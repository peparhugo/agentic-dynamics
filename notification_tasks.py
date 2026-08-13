"""Background tasks used by the task-management API."""

import logging

from celery import Celery


celery_app = Celery("task_management")
celery_app.config_from_object("celery_config")
logger = logging.getLogger(__name__)


@celery_app.task(name="notification_tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock delivery of a task-completion email."""
    logger.info("Task completed notification sent to %s for %s", user_email, task_title)
