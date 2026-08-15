"""Background notification tasks."""

from celery_config import celery_app


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email, task_title):
    """Mock sending a task completion email."""
    print(f"Notification email to {user_email}: task completed - {task_title}")
