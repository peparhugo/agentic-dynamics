"""
Celery tasks for the Task Management API.

Currently just one task: sending a (mocked) notification email to a task's
owner when their task is marked completed. The task is intentionally
side-effect-light (a log/print) so it can run in any environment without
real SMTP credentials; swap the body for a real email provider call when
ready.
"""

import logging

from celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    """Send (mock) a "task completed" notification email.

    Runs asynchronously on a Celery worker so the HTTP request that
    triggered it never blocks waiting on this. For now, "sending" just
    means logging/printing -- swap in a real email provider integration
    (SendGrid, SES, SMTP, etc.) here when one is available.
    """
    message = (
        f"[email notification] To: {user_email} | "
        f"Subject: Task completed | "
        f"Body: Your task '{task_title}' has been marked as completed."
    )
    print(message)
    logger.info(message)
    return message
