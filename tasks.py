"""
Celery tasks for the task management API.
"""

from celery import Celery

celery_app = Celery("task_management")
celery_app.config_from_object("celery_config")


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    message = f"[EMAIL] To: {user_email} | Subject: Task completed | Your task '{task_title}' is now complete."
    print(message)
    return message
