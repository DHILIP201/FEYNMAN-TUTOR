"""
jobs/celery_app.py
===================
Track C — C-5: Celery Background Job Engine (Redis Broker)

Configures Celery application for asynchronous background tasks:
  - Daily study digest notifications
  - 20h streak preservation warnings
  - Weekly learner mastery reports
"""

import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "feynman_jobs",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["jobs.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Periodic schedules (Celery Beat)
    beat_schedule={
        "daily-study-digest": {
            "task": "jobs.tasks.dispatch_daily_digests",
            "schedule": 86400.0,  # Once per day (06:00 UTC in production)
        },
        "streak-preservation-check": {
            "task": "jobs.tasks.check_streak_preservation",
            "schedule": 3600.0,   # Hourly check
        },
    },
)
