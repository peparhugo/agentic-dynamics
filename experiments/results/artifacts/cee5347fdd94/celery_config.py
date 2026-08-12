"""Celery application and asynchronous task definitions."""

import os

from celery import Celery


BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery("task_management")
celery_app.conf.update(
    broker_url=BROKER_URL,
    result_backend=RESULT_BACKEND,
    task_routes={
        "celery_config.send_notification_email": {"queue": "notifications"},
    },
)


@celery_app.task(name="celery_config.send_notification_email")
def send_notification_email(user_email, task_title):
    """Mock delivery of a task-completion notification."""
    print(f"Notification email sent to {user_email}: task '{task_title}' completed")
