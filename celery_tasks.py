"""
Celery tasks for async operations.
"""

from celery import Celery
from celery_config import CeleryConfig

celery = Celery(__name__)
celery.config_from_object(CeleryConfig)


@celery.task(name="celery_tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    """
    Send notification email to user when task is completed.

    This task runs asynchronously and does not block the API response.
    Currently logs to console instead of actually sending email.
    """
    print(f"[NOTIFICATION] Sending email to {user_email}: Task '{task_title}' has been completed")
    return {
        "status": "success",
        "user_email": user_email,
        "task_title": task_title
    }
