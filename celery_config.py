"""Celery configuration for background task processing."""

import os

from celery import Celery


broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
task_routes = {
    "notification_tasks.send_notification_email": {"queue": "notifications"},
}
imports = ("notification_tasks",)

celery_app = Celery("task_management")
celery_app.config_from_object(__name__)
