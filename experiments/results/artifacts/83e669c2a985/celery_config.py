"""Celery application configuration for asynchronous task notifications."""

import os

from celery import Celery


celery_app = Celery("task_api")
celery_app.conf.update(
    broker_url=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    result_backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    task_routes={
        "send_notification_email": {"queue": "notifications"},
    },
)

# This alias makes the configured application convenient for worker commands and imports.
celery = celery_app
