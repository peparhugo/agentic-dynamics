"""Celery application and broker configuration for background notifications."""

import os

from celery import Celery


BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", BROKER_URL)

celery_app = Celery(
    "task_management",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
)
celery_app.conf.update(
    task_routes={
        "tasks.send_notification_email": {"queue": "notifications"},
    },
)
