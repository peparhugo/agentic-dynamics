"""Celery tasks for the task management API."""

import logging

from celery_config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    """Mock email delivery: logs to console instead of actually sending."""
    message = (
        f"Notification email sent to {user_email}: "
        f"task '{task_title}' has been completed."
    )
    logger.info("[EMAIL] %s", message)
    print(f"[EMAIL] {message}")
    return message
