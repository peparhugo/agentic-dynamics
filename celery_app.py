"""Celery application and tasks for asynchronous email notifications."""

import logging

from celery import Celery

import celery_config

celery_app = Celery("tasks_app")
celery_app.config_from_object(celery_config)

logger = logging.getLogger(__name__)


@celery_app.task(name="celery_app.send_notification_email")
def send_notification_email(user_email, task_title):
    """Mock-send a completion notification email (logs/prints instead of a real send)."""
    message = f"[email] To: {user_email} | Subject: Task completed | Body: Your task '{task_title}' has been marked completed."
    logger.info(message)
    print(message)
    return {"user_email": user_email, "task_title": task_title}
