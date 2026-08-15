"""Async email notifications, sent via Celery so the API never blocks on delivery."""

import logging

from celery import Celery

import celery_config

logger = logging.getLogger(__name__)

celery_app = Celery("task_manager")
celery_app.config_from_object(celery_config)


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> dict:
    """Mock email send: logs and prints instead of hitting a real mail provider."""
    message = f"[email] To: {user_email} | Subject: Task completed | Body: Your task '{task_title}' is complete."
    logger.info(message)
    print(message)
    return {"user_email": user_email, "task_title": task_title, "sent": True}
