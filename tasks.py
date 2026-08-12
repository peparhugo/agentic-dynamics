"""Background Celery tasks used by the task management API."""

from celery_config import celery_app


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    """Send a mock completion email without requiring an email provider."""
    print(f"Notification email to {user_email}: task '{task_title}' completed")
