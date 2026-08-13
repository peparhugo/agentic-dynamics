"""
Celery tasks for async operations.
"""

import logging
from celery_config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    """
    Send a notification email when a task is completed.
    Currently mocked to log/print to console.
    """
    message = f"Task completed: '{task_title}' for user {user_email}"
    logger.info(f"[EMAIL NOTIFICATION] {message}")
    print(f"[EMAIL NOTIFICATION] {message}")
    return {"status": "sent", "email": user_email, "task_title": task_title}
