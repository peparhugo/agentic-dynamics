"""Background notification tasks."""

from celery_config import celery_app


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock email delivery used by the notification worker."""
    print(f"Notification email to {user_email}: task completed - {task_title}")
