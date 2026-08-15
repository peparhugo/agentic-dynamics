"""Celery tasks for the task management API."""

import logging

from celery_config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    """Send a notification email to a task owner (mock implementation)."""
    logger.info(
        "Sending notification email to %s for completed task: %s",
        user_email,
        task_title,
    )
    print(f"[notification] Email sent to {user_email} for task '{task_title}'")
    return {"email": user_email, "task_title": task_title}
