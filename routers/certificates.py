"""
api/certificates.py
====================
Track C — C-3: Learning Reports & Certificates

Provides:
  - CertificateRecord ORM model (UUID-keyed, stored in DB)
  - generate_certificate(): creates PDF + persists record
  - verify_certificate(): public safe info for /verify/{uuid} page
  - get_learner_report(): full structured learning progress report

Architecture:
  Student reaches ≥80% mastery on topic
           ↓
  generate_certificate() called
           ↓
  UUID v4 certificate record stored in DB
           ↓
        ┌──┴───┐
        ↓      ↓
  PDF bytes   /verify/{uuid}
              ↓
     Public verification page (no private data)

Zero-secret invariant: never expose raw user_id, session content,
API keys, or other private learning history on the public /verify/ page.
"""

import io
import uuid
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Session
from database import Base, User, TopicMastery, LearnerProfile, LearningEvent, CertificateRecord


# ---------------------------------------------------------------------------
# Mastery tier labels (consistent with Knowledge Map)
# ---------------------------------------------------------------------------

def _mastery_tier(score: int) -> str:
    if score >= 90:
        return "Distinguished"
    if score >= 80:
        return "Mastered"
    if score >= 60:
        return "Proficient"
    return "In Progress"



# ---------------------------------------------------------------------------
# PDF Generation (reportlab)
# ---------------------------------------------------------------------------

def _build_pdf(
    student_name: str,
    topic: str,
    mastery_score: int,
    tier: str,
    cert_uuid: str,
    issued_at: datetime,
) -> bytes:
    """Render a premium dark-mode PDF certificate and return bytes."""
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    # Color palette
    DARK_BG     = colors.HexColor("#0D0D1A")
    PURPLE_MAIN = colors.HexColor("#6C63FF")
    GOLD_ACCENT = colors.HexColor("#F7B731")
    LIGHT_TEXT  = colors.HexColor("#E8E8F0")
    SUBTLE_TEXT = colors.HexColor("#9090B0")

    styles = getSampleStyleSheet()

    def style(name, parent="Normal", **kwargs):
        return ParagraphStyle(name, parent=styles[parent], **kwargs)

    title_style = style("Title", fontSize=36, textColor=GOLD_ACCENT,
                        alignment=TA_CENTER, spaceAfter=4, fontName="Helvetica-Bold")
    brand_style = style("Brand", fontSize=14, textColor=PURPLE_MAIN,
                        alignment=TA_CENTER, spaceAfter=2, fontName="Helvetica-Bold")
    subtitle_style = style("Subtitle", fontSize=11, textColor=SUBTLE_TEXT,
                           alignment=TA_CENTER, spaceAfter=20)
    student_style = style("Student", fontSize=28, textColor=LIGHT_TEXT,
                          alignment=TA_CENTER, spaceAfter=6, fontName="Helvetica-Bold")
    topic_style = style("Topic", fontSize=22, textColor=GOLD_ACCENT,
                        alignment=TA_CENTER, spaceAfter=12, fontName="Helvetica-Bold")
    body_style = style("Body", fontSize=12, textColor=LIGHT_TEXT,
                       alignment=TA_CENTER, spaceAfter=8)
    small_style = style("Small", fontSize=9, textColor=SUBTLE_TEXT,
                        alignment=TA_CENTER, spaceAfter=4)

    story = [
        Spacer(1, 0.3 * cm),
        Paragraph("⚡ FEYNMAN AI", brand_style),
        Paragraph("Certificate of Mastery", title_style),
        HRFlowable(color=PURPLE_MAIN, thickness=1.5, width="80%"),
        Spacer(1, 0.5 * cm),
        Paragraph("This certifies that", subtitle_style),
        Paragraph(student_name, student_style),
        Paragraph("has demonstrated mastery of", body_style),
        Paragraph(topic, topic_style),
        Paragraph(f"Mastery Score: {mastery_score}% — Tier: {tier}", body_style),
        HRFlowable(color=GOLD_ACCENT, thickness=0.5, width="60%"),
        Spacer(1, 0.4 * cm),
        Paragraph(f"Issued: {issued_at.strftime('%B %d, %Y')}", small_style),
        Paragraph(f"Certificate ID: {cert_uuid}", small_style),
        Paragraph("Verify at: feynman.ai/verify/" + cert_uuid, small_style),
    ]

    def draw_background(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(DARK_BG)
        canvas.rect(0, 0, landscape(A4)[0], landscape(A4)[1], fill=1, stroke=0)
        # Purple border
        canvas.setStrokeColor(PURPLE_MAIN)
        canvas.setLineWidth(3)
        canvas.rect(0.5 * cm, 0.5 * cm,
                    landscape(A4)[0] - 1 * cm,
                    landscape(A4)[1] - 1 * cm,
                    fill=0, stroke=1)
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_background, onLaterPages=draw_background)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_certificate(db: Session, user_id: int, topic: str):
    """
    Generate a mastery certificate for `topic` if the user's mastery_score ≥ 80.

    Returns: dict with keys `cert_uuid`, `pdf_bytes`, `public_url`, `tier`.
    Raises ValueError if mastery < 80 or user not found.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    mastery = db.query(TopicMastery).filter(
        TopicMastery.user_id == user_id,
        TopicMastery.canonical_topic == topic,
    ).first()

    if not mastery or mastery.mastery_score < 80:
        score = mastery.mastery_score if mastery else 0
        raise ValueError(
            f"Certificate requires mastery ≥ 80%. Current score for '{topic}': {score}%"
        )

    tier = _mastery_tier(mastery.mastery_score)
    cert_uuid = str(uuid.uuid4())
    issued_at = datetime.now(timezone.utc).replace(tzinfo=None)  # store as naive UTC

    # Check if a certificate already exists for this user+topic (idempotent)
    existing = db.query(CertificateRecord).filter(
        CertificateRecord.user_id == user_id,
        CertificateRecord.topic == topic,
        CertificateRecord.revoked == False,
    ).first()

    if existing:
        cert_uuid = existing.cert_uuid
        issued_at = existing.issued_at
        tier = existing.tier
    else:
        record = CertificateRecord(
            cert_uuid=cert_uuid,
            user_id=user_id,
            student_name=user.name,
            topic=topic,
            mastery_score=mastery.mastery_score,
            tier=tier,
            issued_at=issued_at,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    pdf_bytes = _build_pdf(
        student_name=user.name,
        topic=topic,
        mastery_score=mastery.mastery_score,
        tier=tier,
        cert_uuid=cert_uuid,
        issued_at=issued_at,
    )

    return {
        "cert_uuid": cert_uuid,
        "pdf_bytes": pdf_bytes,
        "public_url": f"/verify/{cert_uuid}",
        "tier": tier,
        "mastery_score": mastery.mastery_score,
    }


def verify_certificate(db: Session, cert_uuid: str) -> Optional[dict]:
    """
    Return publicly safe verification info for a certificate UUID.
    Never exposes raw user_id, session content, or private learning history.
    Returns None if the certificate is not found or has been revoked.
    """
    record = db.query(CertificateRecord).filter(
        CertificateRecord.cert_uuid == cert_uuid,
        CertificateRecord.revoked == False,
    ).first()

    if not record:
        return None

    return {
        "valid": True,
        "student_name": record.student_name,
        "topic": record.topic,
        "mastery_score": record.mastery_score,
        "tier": record.tier,
        "issued_at": record.issued_at.isoformat(),
        "certificate_id": record.cert_uuid,
        "issuer": "Feynman AI",
    }


def get_learner_report(db: Session, user_id: int) -> dict:
    """
    Produce a comprehensive structured learning report for the user.
    Safe to return to the authenticated user — contains their own data.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    profile = db.query(LearnerProfile).filter(LearnerProfile.user_id == user_id).first()
    masteries = db.query(TopicMastery).filter(TopicMastery.user_id == user_id).all()

    topics_out = []
    mastered_count = 0
    total_attempts = 0
    total_correct = 0

    for m in masteries:
        if m.mastery_score >= 80:
            status = "MASTERED"
            mastered_count += 1
        elif m.mastery_score >= 40:
            status = "IN_PROGRESS"
        else:
            status = "NEEDS_ATTENTION"

        total_attempts += m.attempt_count
        total_correct += m.correct_count
        topics_out.append({
            "topic": m.canonical_topic,
            "status": status,
            "mastery_score": m.mastery_score,
            "confidence_score": round(m.confidence_score, 2),
            "attempt_count": m.attempt_count,
            "weak_spots": json.loads(m.weak_spots or "[]"),
            "last_studied_at": m.last_studied_at.isoformat() if m.last_studied_at else None,
        })

    quiz_accuracy = round((total_correct / total_attempts * 100) if total_attempts > 0 else 0, 1)

    # Spaced repetition completion rate
    from datetime import datetime
    now = datetime.utcnow()
    due_topics = [m for m in masteries if m.next_review_at and m.next_review_at <= now]
    overdue_count = len(due_topics)
    completed_rate = round(
        (len(masteries) - overdue_count) / len(masteries)
        if masteries else 1.0, 2
    )

    return {
        "summary": {
            "student_name": user.name,
            "topics_mastered": mastered_count,
            "total_topics_studied": len(masteries),
            "total_xp": user.xp,
            "study_time_minutes": profile.total_study_minutes if profile else 0,
            "quiz_accuracy": quiz_accuracy,
            "current_streak": user.current_streak,
            "longest_streak": user.longest_streak,
        },
        "topics": sorted(topics_out, key=lambda t: t["mastery_score"], reverse=True),
        "spaced_repetition": {
            "completed_rate": completed_rate,
            "overdue_count": overdue_count,
        },
    }
