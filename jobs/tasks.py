"""
jobs/tasks.py
==============
Track C — C-5: Background Job Tasks & Notification Dispatcher

Provides:
  - dispatch_daily_digests(): scans active learners with due spaced repetition items
  - check_streak_preservation(): notifies users at risk of losing their streak
  - send_notification_email(): SMTP delivery with template formatting
"""

import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from database import SessionLocal, User, NotificationPreference, TopicMastery


def send_email_message(to_email: str, subject: str, body_text: str, body_html: str = None) -> bool:
    """
    Sends email via SMTP using environment configuration.
    Falls back gracefully to logging if SMTP is not configured in dev/test.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    if not smtp_host or not smtp_user:
        # Dev / test environment: log and succeed
        print(f"[EMAIL MOCK] To: {to_email} | Subject: {subject} | Body: {body_text[:60]}...")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Feynman Tutor AI <{smtp_user}>"
        msg["To"] = to_email

        msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send to {to_email}: {e}")
        return False


def dispatch_daily_digests() -> dict:
    """
    Scans users with email_digest enabled and spaced reviews due today.
    """
    db = SessionLocal()
    sent_count = 0
    now = datetime.utcnow()

    try:
        prefs = db.query(NotificationPreference).filter(
            NotificationPreference.email_digest == True
        ).all()

        for pref in prefs:
            user = db.query(User).filter(User.id == pref.user_id).first()
            if not user or not user.email:
                continue

            due_topics = db.query(TopicMastery).filter(
                TopicMastery.user_id == user.id,
                TopicMastery.next_review_at <= now,
            ).all()

            if due_topics:
                topic_names = ", ".join(t.canonical_topic for t in due_topics[:3])
                subject = f"⚡ Feynman AI: {len(due_topics)} topics ready for review today"
                body = (
                    f"Hi {user.name},\n\n"
                    f"You have {len(due_topics)} topic(s) due for spaced review: {topic_names}.\n"
                    f"Strengthen your neural pathways in just 5 minutes today!\n\n"
                    f"Start session: https://feynman.ai/\n"
                )
                if send_email_message(user.email, subject, body):
                    sent_count += 1

        return {"dispatched": sent_count, "timestamp": now.isoformat()}
    finally:
        db.close()


def check_streak_preservation() -> dict:
    """
    Warns users who have an active streak but haven't studied in the last 20 hours.
    """
    db = SessionLocal()
    warned_count = 0
    now = datetime.utcnow()
    threshold = now - timedelta(hours=20)
    today_str = now.strftime("%Y-%m-%d")

    try:
        prefs = db.query(NotificationPreference).filter(
            NotificationPreference.streak_reminders == True
        ).all()

        for pref in prefs:
            user = db.query(User).filter(
                User.id == pref.user_id,
                User.current_streak > 0,
                User.last_study_date != today_str,
            ).first()

            if user and user.email:
                subject = f"🔥 Keep your {user.current_streak}-day Feynman streak alive!"
                body = (
                    f"Hey {user.name},\n\n"
                    f"Your {user.current_streak}-day study streak will expire soon if you don't complete a quick learning check-in today.\n\n"
                    f"Keep it going: https://feynman.ai/\n"
                )
                if send_email_message(user.email, subject, body):
                    warned_count += 1

        return {"streak_warnings_sent": warned_count, "timestamp": now.isoformat()}
    finally:
        db.close()
