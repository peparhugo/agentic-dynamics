"""Celery application and task definitions."""

from celery import Celery

import celery_config

celery_app = Celery("tasks")
celery_app.config_from_object(celery_config)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str):
    """Send a notification email to a task owner (mocked as a console log)."""
    print(
        f"[EMAIL] Notification sent to {user_email}: "
        f"your task '{task_title}' was completed"
    )
    return {"user_email": user_email, "task_title": task_title}
