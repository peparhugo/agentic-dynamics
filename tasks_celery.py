"""
Celery tasks for the Task Management API
"""

from celery import Celery
import celery_config

celery_app = Celery(__name__)
celery_app.config_from_object(celery_config)


@celery_app.task(name="tasks_celery.send_notification_email")
def send_notification_email(user_email, task_title):
    """
    Send a notification email to the task owner when a task is completed.

    In production, this would integrate with an email service (e.g., SendGrid, AWS SES).
    For now, we log/print the notification.
    """
    message = f"Task '{task_title}' has been marked as completed!"
    print(f"[EMAIL NOTIFICATION] Sending email to {user_email}: {message}")
    return {
        "status": "sent",
        "recipient": user_email,
        "message": message,
    }
