"""Celery tasks for sending email notifications."""

import logging

from celery_config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="email_tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    """Mock email sender: log the notification instead of sending for real."""
    message = f"Notification email sent to {user_email}: task '{task_title}' completed."
    print(message)
    logger.info(message)
    return message
