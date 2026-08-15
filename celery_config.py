"""Celery application and worker configuration."""

import os

from celery import Celery


celery = Celery("task_management")
celery.conf.update(
    broker_url=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    result_backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    task_routes={
        "tasks.send_notification_email": {"queue": "notifications"},
    },
)
