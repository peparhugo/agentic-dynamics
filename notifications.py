"""Celery app and tasks for sending async notification emails."""

import logging

from celery import Celery

import celery_config

celery_app = Celery("taskapp")
celery_app.config_from_object(celery_config)

logger = logging.getLogger(__name__)


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    """Mock email send: logs/prints instead of hitting a real mail provider."""
    message = f"[notification] Emailing {user_email}: your task '{task_title}' is completed"
    print(message)
    logger.info(message)
    return message
