"""Celery application and email notification tasks."""

from celery import Celery

import celery_config

celery_app = Celery("tasks")
celery_app.config_from_object(celery_config)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> dict:
    """Mock email sender — prints a notification to the console/log."""
    print(
        f"[email] Task completed notification sent to {user_email}: "
        f"'{task_title}' is done."
    )
    return {"user_email": user_email, "task_title": task_title}
