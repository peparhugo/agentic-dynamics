"""Celery tasks for the task management API."""

import logging

from celery_config import celery_app

logger = logging.getLogger(__name__)


def send_email(user_email: str, task_title: str) -> None:
    """Mock email sender: log and print the notification."""
    message = f"Task '{task_title}' completed - notification email sent to {user_email}"
    logger.info(message)
    print(message)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str):
    """Send a notification email to the task owner (mocked for now)."""
    send_email(user_email, task_title)
