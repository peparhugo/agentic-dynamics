"""Celery configuration for the task management API.

Uses Redis as the message broker and result backend.
"""

import os

from celery import Celery

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "task_api",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["email_tasks"],
)

celery_app.conf.update(
    task_routes={
        "email_tasks.send_notification_email": {"queue": "email"},
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
)
