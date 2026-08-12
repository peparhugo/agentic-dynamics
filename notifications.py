"""Asynchronous task notifications."""

from celery import Celery


celery_app = Celery("task_notifications")
celery_app.config_from_object("celery_config")


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email, task_title):
    """Mock email delivery performed by a Celery worker."""
    print(f"Notification email to {user_email}: task '{task_title}' completed")
