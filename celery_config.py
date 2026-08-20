"""
Celery configuration.

Defines the Celery application instance with a Redis broker and result
backend, plus task routing rules for the notification queue.
"""

import os

from celery import Celery

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "tasks_api",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_track_started=True,
)

celery_app.conf.task_routes = {
    "tasks.send_notification_email": {"queue": "email"},
}
