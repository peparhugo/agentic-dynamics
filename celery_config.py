"""Celery application configuration for asynchronous notifications."""

import os

from celery import Celery


broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", broker_url)

celery_app = Celery("task_management", broker=broker_url, backend=result_backend)
celery_app.conf.update(
    task_routes={"notifications.send_notification_email": {"queue": "notifications"}},
)
