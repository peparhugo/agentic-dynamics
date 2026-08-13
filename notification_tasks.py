"""Background tasks for task-management notifications."""

import logging

from celery import Celery

import celery_config


celery_app = Celery("task_notifications")
celery_app.config_from_object(celery_config)
logger = logging.getLogger(__name__)


@celery_app.task(name="notification_tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    """Mock email delivery until a mail provider is configured."""
    logger.info("Task completed notification sent to %s for task %s", user_email, task_title)
