"""Background jobs used by the task management API."""

from celery_config import celery_app


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    """Mock delivery of a task-completion email."""
    print(f"Notification email sent to {user_email}: task completed: {task_title}")
