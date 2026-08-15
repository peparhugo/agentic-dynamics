"""
Celery tasks for async notifications.
"""

from celery import Celery
from celery_config import CeleryConfig

celery_app = Celery(__name__)
celery_app.config_from_object(CeleryConfig)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    """
    Send a notification email to the task owner when task is completed.
    Mock implementation: logs to console.

    Args:
        user_email: Email address of the task owner
        task_title: Title of the completed task
    """
    print(f"[EMAIL NOTIFICATION] Sent to {user_email}: Task '{task_title}' has been completed!")
    return {"status": "sent", "email": user_email, "task": task_title}
