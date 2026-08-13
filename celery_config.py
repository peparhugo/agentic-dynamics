"""Celery configuration for asynchronous task notifications."""

import os

from celery import Celery


celery_app = Celery(
    "task_notifications",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)
celery_app.conf.update(
    task_routes={
        "notification_tasks.send_notification_email": {"queue": "notifications"},
    }
)
