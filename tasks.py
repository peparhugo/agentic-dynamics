"""
Celery tasks for the task management API.
"""

import logging

from celery_config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> None:
    """Send a notification email (mocked) to the task owner."""
    message = (
        f"[EMAIL] To: {user_email} | Subject: Task completed | "
        f"Your task '{task_title}' has been completed."
    )
    logger.info(message)
    print(message)
