"""Celery application configuration for asynchronous notifications."""

import os

from celery import Celery


celery_app = Celery(
    "task_management",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
)
celery_app.conf.update(
    task_routes={"tasks.send_notification_email": {"queue": "notifications"}},
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
