"""Celery configuration and background notification tasks."""

import logging
import os

from celery import Celery


broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
task_routes = {
    "celery_config.send_notification_email": {"queue": "notifications"},
}

celery_app = Celery("task_management", broker=broker_url, backend=result_backend)
celery_app.conf.update(task_routes=task_routes)


@celery_app.task
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock delivery until an email provider is configured."""
    logging.getLogger(__name__).info(
        "Task completed notification sent to %s for %s", user_email, task_title
    )
