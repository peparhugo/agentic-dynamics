"""
Celery configuration for the Task Management API's async notification system.

All settings can be overridden via environment variables so the same config
works in dev, tests, and production without code changes.
"""

import os


# ── Broker / result backend (Redis) ─────────────────────────────
broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# ── Serialization ────────────────────────────────────────────────
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True

# ── Task routing ─────────────────────────────────────────────────
# Route notification emails to their own queue so they can be scaled /
# monitored independently from other (future) background work.
task_routes = {
    "tasks.send_notification_email": {"queue": "email_notifications"},
}

# ── Misc reliability settings ────────────────────────────────────
task_acks_late = True
worker_prefetch_multiplier = 1
task_track_started = True
