"""
Celery application for the task management API.

Defines the async notification task that is triggered when a task's
status changes to 'completed'. Email sending is mocked (logged/printed)
since no real mail provider is wired up.
"""

from celery import Celery

celery_app = Celery("task_manager")
celery_app.config_from_object("celery_config")


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    message = f"[notification] Sending email to {user_email}: task '{task_title}' is complete."
    print(message)
    return message
