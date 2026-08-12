"""
Celery application instance and the background email notification task.
"""

from celery import Celery

import celery_config

celery_app = Celery("task_api")
celery_app.config_from_object(celery_config)


@celery_app.task
def send_notification_email(user_email: str, task_title: str) -> None:
    """
    Send a notification email when a task is completed.

    This is a mock implementation that writes to stdout.
    """
    print(
        f"[notification] Sending email to {user_email}: "
        f"task '{task_title}' was completed"
    )
