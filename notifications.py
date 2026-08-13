"""Async email notifications, sent via Celery so the API never blocks on them."""
import logging

from celery import Celery

import celery_config

celery_app = Celery("notifications")
celery_app.config_from_object(celery_config)

logger = logging.getLogger(__name__)


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> None:
    message = f"[email] To: {user_email} | Subject: Task completed | Your task '{task_title}' is complete."
    logger.info(message)
    print(message)
