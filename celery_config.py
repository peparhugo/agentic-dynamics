"""Celery configuration for the task management API.

Uses Redis as the message broker and result backend. Values can be
overridden via environment variables.
"""

import os

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

task_routes = {
    "app.send_notification_email": {"queue": "emails"},
}

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True
