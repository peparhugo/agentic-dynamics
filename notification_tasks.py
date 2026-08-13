"""Background tasks for task notifications."""

import logging

from celery import Celery

import celery_config


logger = logging.getLogger(__name__)

celery_app = Celery("task_notifications")
celery_app.config_from_object(celery_config)


@celery_app.task
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock delivery of a completion notification email."""
    logger.info("Sending completion notification for %r to %s", task_title, user_email)
