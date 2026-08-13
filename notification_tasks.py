"""Asynchronous notification tasks."""

from celery import Celery


celery_app = Celery("task_management")
celery_app.config_from_object("celery_config")


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock delivery until an email provider is configured."""
    print(f"Email to {user_email}: Task completed - {task_title}")
