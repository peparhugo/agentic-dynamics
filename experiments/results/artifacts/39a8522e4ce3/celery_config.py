"""Celery application configuration for asynchronous task notifications."""

import os

from celery import Celery


REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "task_management",
    broker=os.environ.get("CELERY_BROKER_URL", REDIS_URL),
    backend=os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL),
)
celery_app.conf.update(
    task_routes={
        "tasks.send_notification_email": {"queue": "notifications"},
    },
)

# A conventional short alias is useful for Celery CLI integrations.
app = celery_app
