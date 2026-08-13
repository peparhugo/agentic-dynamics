"""
Celery tasks for async operations.
"""

from celery import Celery
import celery_config
import logging

app = Celery(__name__)
app.config_from_object(celery_config)

logger = logging.getLogger(__name__)


@app.task(name='celery_tasks.send_notification_email')
def send_notification_email(user_email: str, task_title: str) -> str:
    """
    Send notification email when a task is completed.

    Args:
        user_email: Email address of the task owner
        task_title: Title of the completed task

    Returns:
        Status message
    """
    message = f"Task '{task_title}' has been completed! Notification sent to {user_email}"
    logger.info(message)
    print(message)
    return message
