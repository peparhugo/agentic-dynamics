"""Celery configuration for the task management API.

Uses Redis as the message broker and result backend. The connection URL can be
overridden with the REDIS_URL environment variable.
"""

import os

from celery import Celery

BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "task_management",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_default_queue="default",
    task_routes={
        "tasks.send_notification_email": {"queue": "email"},
    },
)
