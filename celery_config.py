"""Celery application configuration for background notifications."""

import os

from celery import Celery


REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("task_notifications")
celery_app.conf.update(
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
    task_routes={
        "notifications.send_notification_email": {
            "queue": "notifications",
        }
    },
)
