"""
Celery tasks for async operations
"""

from celery import Celery
import logging

logger = logging.getLogger(__name__)

app = Celery("task_app")
app.config_from_object("celery_config")


@app.task(name="tasks_celery.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    """
    Send a notification email to the task owner when their task is completed.

    Args:
        user_email: Email address of the task owner
        task_title: Title of the completed task

    Returns:
        Success message with details
    """
    message = f"📧 Email notification sent to {user_email}: Task '{task_title}' has been completed."
    print(message)
    logger.info(message)
    return message
