"""Background notification tasks."""

from celery_config import celery_app


@celery_app.task(name="notification_tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    """Mock delivery of a task-completion notification email."""
    print(f"Notification email sent to {user_email}: task completed - {task_title}")
