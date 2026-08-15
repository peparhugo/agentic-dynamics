"""Celery application configuration for background notifications."""

import os

from celery import Celery


BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", BROKER_URL)

celery_app = Celery("task_management")
celery_app.conf.update(
    broker_url=BROKER_URL,
    result_backend=RESULT_BACKEND,
    task_routes={
        "notifications.send_notification_email": {"queue": "notifications"},
    },
)
