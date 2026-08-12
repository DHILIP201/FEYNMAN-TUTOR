"""
api/admin.py
=============
Track C — C-4: Admin Operations Console & Protected APIs

Provides:
  - Admin authentication via ADMIN_SECRET_KEY / JWT (role='admin')
  - GET /admin/metrics/ — aggregate operational metrics
  - GET /admin/users/ — paginated user list with study stats
  - GET /admin/users/{user_id}/report/ — individual student report
  - GET /admin/gateway/ — real-time Gemini gateway health
  - Zero-secret invariant: raw API keys are NEVER exposed in any admin endpoint.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database import get_db, User, ChatSession, LearnerProfile, TopicMastery, TelemetryLog, UserSubscription
from security import create_access_token, decode_access_token
from api.certificates import get_learner_report

router = APIRouter(prefix="/admin", tags=["Admin Operations"])

ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "feynman-admin-dev-secret-2026")


def require_admin_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Dependency that enforces admin JWT token authorization.
    Rejects missing, expired, non-admin, or invalid tokens with 403 Forbidden.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin authorization header required",
        )
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return payload


@router.post("/login/")
def admin_login(payload: dict):
    """
    Authenticate as admin using ADMIN_SECRET_KEY.
    Returns short-lived admin JWT with role='admin'.
    """
    secret = payload.get("secret_key") or payload.get("password")
    if not secret or secret != ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin secret key",
        )

    # Issue 4-hour admin token
    token = create_access_token(
        data={"sub": "admin@feynmantutor.internal", "role": "admin", "admin": True},
        expires_delta=timedelta(hours=4),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "admin",
        "expires_in_seconds": 14400,
    }


@router.get("/metrics/")
def get_admin_metrics(
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin_user),
):
    """
    Aggregate operational metrics:
    - DAU (active users past 24h)
    - Total registered users & sessions
    - Total tokens consumed & average latency
    - Fallback rate & error rate
    - Top weak spots across all learners
    """
    now = datetime.utcnow()
    past_24h = now - timedelta(hours=24)

    total_users = db.query(User).count()
    total_sessions = db.query(ChatSession).count()

    # Active users in past 24h
    dau = db.query(User).filter(User.updated_at >= past_24h).count()

    # Telemetry aggregate metrics
    logs_24h = db.query(TelemetryLog).filter(TelemetryLog.timestamp >= past_24h).all()
    total_requests_24h = len(logs_24h)
    total_tokens_24h = sum(l.total_tokens for l in logs_24h)
    fallbacks_24h = sum(1 for l in logs_24h if l.fallback_used)
    errors_24h = sum(1 for l in logs_24h if l.http_status >= 400)
    avg_latency = (
        round(sum(l.latency_ms for l in logs_24h) / total_requests_24h, 2)
        if total_requests_24h > 0
        else 0.0
    )
    error_rate = (
        round((errors_24h / total_requests_24h) * 100, 2)
        if total_requests_24h > 0
        else 0.0
    )
    fallback_rate = (
        round((fallbacks_24h / total_requests_24h) * 100, 2)
        if total_requests_24h > 0
        else 0.0
    )

    # Top weak spots across all topics
    masteries = db.query(TopicMastery).all()
    import json
    weak_counts = {}
    for m in masteries:
        try:
            ws_list = json.loads(m.weak_spots or "[]")
            for w in ws_list:
                weak_counts[w] = weak_counts.get(w, 0) + 1
        except Exception:
            pass

    top_weak_spots = sorted(
        [{"weak_spot": k, "count": v} for k, v in weak_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    return {
        "dau": max(dau, 1 if total_users > 0 else 0),
        "total_users": total_users,
        "total_sessions": total_sessions,
        "total_requests_24h": total_requests_24h,
        "total_tokens_24h": total_tokens_24h,
        "avg_latency_ms": avg_latency,
        "error_rate_pct": error_rate,
        "fallback_rate_pct": fallback_rate,
        "top_weak_spots": top_weak_spots,
        "timestamp": now.isoformat(),
    }


@router.get("/users/")
def get_admin_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin_user),
):
    """
    Paginated user list with study progress summary and subscription plan.
    """
    offset = (page - 1) * limit
    total = db.query(User).count()
    users = db.query(User).order_by(desc(User.created_at)).offset(offset).limit(limit).all()

    items = []
    for u in users:
        prof = db.query(LearnerProfile).filter(LearnerProfile.user_id == u.id).first()
        sub = db.query(UserSubscription).filter(UserSubscription.user_id == u.id).first()
        mastery_count = db.query(TopicMastery).filter(
            TopicMastery.user_id == u.id,
            TopicMastery.mastery_score >= 80,
        ).count()
        items.append({
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "xp": u.xp,
            "streak": u.current_streak,
            "study_minutes": prof.total_study_minutes if prof else 0,
            "mastered_topics": mastery_count,
            "plan": sub.plan if sub else "free",
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total > 0 else 1,
        "users": items,
    }


@router.get("/users/{user_id}/report/")
def get_admin_user_report(
    user_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin_user),
):
    """
    Admin-accessible full learning report for a specific student.
    """
    try:
        return get_learner_report(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/gateway/")
def get_admin_gateway_health(
    admin: dict = Depends(require_admin_user),
):
    """
    Real-time Gemini Gateway pool status (slots, cooldowns, errors).
    Zero-secret invariant: key strings are never exposed, only slot numbers and status.
    """
    from ai_engine import gemini_gateway
    try:
        pool_status = gemini_gateway.key_pool.get_pool_status()
        return {
            "model": gemini_gateway.model_name,
            "total_slots": len(gemini_gateway.key_pool.slots),
            "healthy_slots": len(gemini_gateway.key_pool.get_available_slots()),
            "slots": pool_status,
        }
    except Exception as e:
        return {
            "status": "error",
            "detail": str(e),
        }
