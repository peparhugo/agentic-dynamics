"""Background notification tasks."""

from celery_config import celery_app


@celery_app.task
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock sending a task-completion email."""
    print(f"Task completed: '{task_title}' notification sent to {user_email}")
