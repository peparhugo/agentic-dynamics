"""Celery tasks for async email notifications."""

from celery import Celery
import celery_config

celery_app = Celery(__name__)
celery_app.config_from_object(celery_config)


@celery_app.task(name="celery_tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str):
    """
    Send notification email to task owner.
    Mocked implementation that logs to console.
    """
    message = f"[EMAIL NOTIFICATION] Sent to {user_email}: Task '{task_title}' has been completed."
    print(message)
    return message
