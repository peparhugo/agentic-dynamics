"""
Celery task for sending (mocked) task-completion notification emails.
"""

import logging

from celery import Celery

import celery_config

logger = logging.getLogger(__name__)

celery_app = Celery("task_manager")
celery_app.config_from_object(celery_config)


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    message = f"[notification] Task '{task_title}' completed - emailing {user_email}"
    print(message)
    logger.info(message)
    return message
