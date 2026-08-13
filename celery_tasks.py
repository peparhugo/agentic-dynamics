"""
Celery application and background tasks for the task management API.

Run a worker with: celery -A celery_tasks worker --loglevel=info
"""

import logging

from celery import Celery

celery_app = Celery("tasks_api")
celery_app.config_from_object("celery_config")

logger = logging.getLogger(__name__)


@celery_app.task(name="celery_tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    message = f"[email] To: {user_email} — your task '{task_title}' is now completed."
    logger.info(message)
    print(message)
    return message
