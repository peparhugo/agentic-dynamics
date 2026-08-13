"""
Celery tasks for async email notifications.
"""

from celery_config import celery_app


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str):
    """
    Send a notification email when a task is completed.

    Args:
        user_email: Email address of the task owner
        task_title: Title of the completed task
    """
    # Mock email sending - in production, would use a real email service
    message = f"[NOTIFICATION] Task completed: {task_title} (sent to {user_email})"
    print(message)
    return {"status": "success", "message": message, "email": user_email, "task": task_title}
