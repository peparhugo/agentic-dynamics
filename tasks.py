"""Celery tasks for the task management API."""

import logging

from celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    """Mock-send a "task completed" notification email.

    Real mail delivery isn't wired up; this logs/prints the message so the
    async dispatch path can be exercised end-to-end without a mail provider.
    """
    message = (
        f"[email] To: {user_email} | Subject: Task completed | "
        f"Body: Your task '{task_title}' is now complete."
    )
    logger.info(message)
    print(message)
    return message
