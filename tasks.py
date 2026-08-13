"""Celery tasks for async operations."""
from celery import Celery
from celery_config import Config

celery_app = Celery(__name__)
celery_app.config_from_object(Config)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> dict:
    """
    Send a notification email when a task is completed.

    Mock implementation: logs to console and returns task details.
    In a real app, this would use an email service.
    """
    message = f"[EMAIL NOTIFICATION] Task '{task_title}' completed. Sent to {user_email}"
    print(message)
    return {"status": "sent", "email": user_email, "task": task_title}
