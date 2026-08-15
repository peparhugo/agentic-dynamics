"""Celery application and asynchronous tasks for the task management API."""

from celery import Celery

import celery_config

celery_app = Celery("tasks")
celery_app.config_from_object(celery_config)


@celery_app.task(name="send_notification_email")
def send_notification_email(user_email, task_title):
    """Send a notification email (mock — logs to console)."""
    print(
        f"[EMAIL] Task '{task_title}' completed. "
        f"Notification sent to {user_email}."
    )
    return {"to": user_email, "title": task_title}
