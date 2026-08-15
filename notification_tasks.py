"""Background tasks for task management notifications."""

import logging

from celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task
def send_notification_email(user_email: str, task_title: str) -> None:
    """Send a completion notification for a task owner.

    Email delivery is mocked until an email provider is configured.
    """
    logger.info("Task %r was completed; notifying %s", task_title, user_email)
