"""Celery app and background tasks for user-facing notifications.

Kept separate from tasks_api.py so the Flask app only needs to import the
task signature to enqueue work; the actual worker process imports this
module directly (`celery -A notifications worker`).
"""

import logging

from celery import Celery

import celery_config

logger = logging.getLogger(__name__)

celery_app = Celery("task_notifications")
celery_app.config_from_object(celery_config)


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email, task_title):
    """Mock email send: logs/prints instead of talking to a real mail server."""
    message = f"[email] To: {user_email} | Subject: Task completed | Body: Your task '{task_title}' is now completed."
    print(message)
    logger.info(message)
    return {"to": user_email, "task_title": task_title, "status": "sent"}
