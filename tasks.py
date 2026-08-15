"""Asynchronous background tasks for the task management API."""

from celery_config import celery


@celery.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> None:
    """Send a task completion notification (mocked until an email provider is added)."""
    print(f"Notification email to {user_email}: task '{task_title}' completed")
