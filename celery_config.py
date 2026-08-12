"""
Celery configuration for the Task Management API's async notification system.

The broker/result backend default to a local Redis instance but can be
overridden via environment variables (e.g. in production or CI).
"""

import os

# ── Broker / result backend ─────────────────────────────────────
broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# ── Serialization ────────────────────────────────────────────────
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True

# ── Task routing ──────────────────────────────────────────────────
# Route notification-related tasks to their own queue so they can be
# scaled/monitored independently of other background work.
task_routes = {
    "tasks.send_notification_email": {"queue": "notifications"},
}

# Keep task results around briefly for debugging; notifications are
# fire-and-forget so we don't need them stored long-term.
result_expires = 3600
