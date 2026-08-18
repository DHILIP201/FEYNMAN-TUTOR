"""
api/billing.py
===============
Track C — C-6: Billing & Subscriptions (Stripe Integration)

Provides:
  - User subscription status query
  - Stripe Checkout Session creation for Pro upgrades
  - Stripe Webhook listener for subscription lifecycle events
  - Zero-secret invariant: STRIPE_SECRET_KEY is read strictly server-side.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database import get_db, User, UserSubscription
from security import decode_access_token

router = APIRouter(prefix="/billing", tags=["Billing & Subscriptions"])

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID", "price_pro_monthly")


def get_current_user_from_header(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = db.query(User).filter(User.email == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_user_plan(db: Session, user_id: int) -> str:
    """Helper to resolve current active plan ('free' or 'pro')."""
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
    if not sub:
        return "free"
    if sub.expires_at and sub.expires_at < datetime.utcnow():
        return "free"
    return sub.plan or "free"


@router.get("/status/")
def get_subscription_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_from_header),
):
    """
    Returns the user's active subscription tier and limits.
    """
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
    plan = get_user_plan(db, user.id)

    return {
        "user_id": user.id,
        "plan": plan,
        "is_pro": plan == "pro",
        "started_at": sub.started_at.isoformat() if sub and sub.started_at else None,
        "expires_at": sub.expires_at.isoformat() if sub and sub.expires_at else None,
        "entitlements": {
            "daily_ai_queries": "unlimited" if plan == "pro" else 10,
            "multi_subject_access": True,
            "pdf_certificates": plan == "pro",
            "weekly_reports": plan == "pro",
            "priority_key_slot": plan == "pro",
        },
    }


@router.post("/create-checkout/")
def create_checkout_session(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_from_header),
):
    """
    Creates a Stripe Checkout Session for upgrading to Feynman AI Pro.
    Returns checkout URL or a mock URL in dev environments.
    """
    if not STRIPE_SECRET_KEY:
        # Dev / test mock checkout flow
        mock_checkout_url = f"/billing/mock-checkout?user_id={user.id}"
        return {
            "checkout_url": mock_checkout_url,
            "session_id": f"mock_cs_{user.id}_{int(datetime.utcnow().timestamp())}",
            "mode": "dev_mock",
        }

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        host = str(request.base_url).rstrip("/")
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": PRO_PRICE_ID, "quantity": 1}],
            mode="subscription",
            customer_email=user.email,
            client_reference_id=str(user.id),
            success_url=f"{host}/?payment=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{host}/?payment=cancelled",
        )
        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "mode": "stripe_live",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe checkout error: {str(e)}",
        )


@router.post("/webhook/")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe webhook handler for subscription lifecycle events.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET:
        try:
            import stripe
            stripe.api_key = STRIPE_SECRET_KEY
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Webhook signature error: {e}")
    else:
        # Dev / test JSON payload parse
        import json
        try:
            event = json.loads(payload.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = event.get("type", "")

    if event_type == "checkout.session.completed":
        session_obj = event.get("data", {}).get("object", {})
        client_ref = session_obj.get("client_reference_id")
        cust_id = session_obj.get("customer")

        if client_ref:
            try:
                user_id = int(client_ref)
                sub = db.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
                if not sub:
                    sub = UserSubscription(
                        user_id=user_id,
                        plan="pro",
                        started_at=datetime.utcnow(),
                        expires_at=datetime.utcnow() + timedelta(days=30),
                        stripe_customer_id=cust_id,
                    )
                    db.add(sub)
                else:
                    sub.plan = "pro"
                    sub.started_at = datetime.utcnow()
                    sub.expires_at = datetime.utcnow() + timedelta(days=30)
                    if cust_id:
                        sub.stripe_customer_id = cust_id
                db.commit()
            except Exception as err:
                print(f"[BILLING ERROR] checkout.session.completed update failed: {err}")

    elif event_type == "customer.subscription.updated":
        sub_obj = event.get("data", {}).get("object", {})
        cust_id = sub_obj.get("customer")
        status_val = sub_obj.get("status")
        if cust_id:
            sub = db.query(UserSubscription).filter(
                UserSubscription.stripe_customer_id == cust_id
            ).first()
            if sub:
                if status_val == "active":
                    sub.plan = "pro"
                elif status_val in ("canceled", "unpaid", "past_due"):
                    sub.plan = "free"
                db.commit()

    elif event_type == "customer.subscription.deleted":
        sub_obj = event.get("data", {}).get("object", {})
        cust_id = sub_obj.get("customer")
        if cust_id:
            sub = db.query(UserSubscription).filter(
                UserSubscription.stripe_customer_id == cust_id
            ).first()
            if sub:
                sub.plan = "free"
                sub.expires_at = datetime.utcnow()
                db.commit()

    return {"status": "success", "event": event_type}

