"""
Celery application and background tasks for the Task Management API.

Currently provides a single task, ``send_notification_email``, which is
triggered whenever a task's status transitions to 'completed'. Sending is
mocked (logged/printed) since there's no real SMTP/email provider wired up
in this environment, but the task is structured so a real email backend
could be dropped in later without changing the calling code.
"""

import logging

from celery import Celery

import celery_config

logger = logging.getLogger(__name__)

celery_app = Celery("task_manager")
celery_app.config_from_object(celery_config)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> dict:
    """Send (mocked) a notification email to ``user_email`` about
    ``task_title`` being completed.

    In production this would integrate with a real email provider (SES,
    SendGrid, SMTP, etc.). For now we just log/print the message so the
    async flow can be exercised and verified end-to-end.
    """
    message = (
        f"[email] To: {user_email} | Subject: Task completed | "
        f"Body: Your task '{task_title}' has been marked as completed."
    )
    print(message)
    logger.info(message)
    return {"to": user_email, "task_title": task_title, "status": "sent"}
