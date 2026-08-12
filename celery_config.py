"""Celery configuration for background notification work."""

import os

from celery import Celery


BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", BROKER_URL)

celery_app = Celery("task_management")
celery_app.conf.update(
    broker_url=BROKER_URL,
    result_backend=RESULT_BACKEND,
    task_routes={
        "notification_tasks.send_notification_email": {"queue": "notifications"},
    },
)

# Keep a conventional short name available for Celery workers and integrations.
celery = celery_app
