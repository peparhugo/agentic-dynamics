"""Asynchronous Celery tasks used by the task API."""

import logging

from celery_config import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(name="send_notification_email")
def send_notification_email(user_email, task_title):
    """Send a completion notification (mocked by logging the message)."""
    logger.info("Task completed notification for %s: %s", user_email, task_title)
    print(f"Email to {user_email}: task '{task_title}' has been completed")
