"""Asynchronous notification tasks."""

from celery import Celery


celery_app = Celery("task_management")
celery_app.config_from_object("celery_config")


@celery_app.task
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock sending a task-completion email."""
    print(f"Notification email sent to {user_email}: task '{task_title}' completed")
