"""
Async email notifications, sent via Celery so the API never blocks on them.
"""

import logging

from celery import Celery

import celery_config

logger = logging.getLogger(__name__)

celery_app = Celery("notifications")
celery_app.config_from_object(celery_config)


@celery_app.task(name="send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    # Mock email send: real delivery would plug an SMTP/API client in here.
    message = f"[email] To: {user_email} — your task '{task_title}' is complete."
    print(message)
    logger.info(message)
    return message
