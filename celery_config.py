"""Celery configuration for asynchronous task notifications."""

import os

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
task_routes = {
    "notifications.send_notification_email": {"queue": "notifications"},
}
