"""Celery tasks for the task management API."""

import logging

from celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    """Mock email notification. Logs instead of sending a real email."""
    message = f"Notification email sent to {user_email} for task '{task_title}'"
    logger.info(message)
    print(message)
    return message
