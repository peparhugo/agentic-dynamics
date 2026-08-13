"""Background tasks for task-owner notifications."""

from celery_config import celery_app


@celery_app.task
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock sending a task completion email."""
    print(f"Notification email sent to {user_email}: Task completed - {task_title}")
