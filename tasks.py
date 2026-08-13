"""Asynchronous jobs for the task management API."""

import logging

from celery import Celery


celery_app = Celery("task_notifications")
celery_app.config_from_object("celery_config")
logger = logging.getLogger(__name__)


@celery_app.task
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock sending a completion notification to a task owner."""
    logger.info("Sending completion notification to %s for task %r", user_email, task_title)
