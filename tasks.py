"""Background tasks for the task management API."""

from celery_config import celery_app


@celery_app.task
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock sending a completion notification email."""
    print(f"Notification email sent to {user_email}: task '{task_title}' completed")
