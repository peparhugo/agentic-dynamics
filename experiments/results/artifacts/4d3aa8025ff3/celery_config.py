"""Celery configuration for the task notification worker."""

import os


CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
)
CELERY_TASK_ROUTES = {
    "notifications.send_notification_email": {"queue": "notifications"}
}
