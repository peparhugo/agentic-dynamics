"""
Celery tasks for the task management API.
"""

from celery_app import celery_app


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    """Send (mock) a notification email that a task was completed.

    Real email delivery is out of scope here; the task just logs the
    notification so the async trigger path can be exercised and tested.
    """
    message = f"[EMAIL] To: {user_email} | Subject: Task completed | Your task '{task_title}' is now complete."
    print(message)
    return message
