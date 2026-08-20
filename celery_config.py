"""Celery configuration for the task management API.

Defines the message broker, result backend, and task routing rules.
"""

import os

from celery import Celery

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "task_management",
    broker=broker_url,
    backend=result_backend,
)

celery_app.conf.update(
    task_routes={
        "tasks.send_notification_email": {"queue": "email"},
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
