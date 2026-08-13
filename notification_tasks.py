"""Background jobs for task-management notifications."""

import logging

from celery_config import celery_app


logger = logging.getLogger(__name__)


@celery_app.task
def send_notification_email(user_email, task_title):
    """Mock delivery of a task completion email."""
    logger.info("Task %r was completed; notifying %s", task_title, user_email)
