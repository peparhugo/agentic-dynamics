"""
Celery application and async tasks for the task management API.
"""

import logging

from celery import Celery

from celery_config import CeleryConfig

logger = logging.getLogger(__name__)

celery = Celery("taskmanager", include=["celery_app"])
celery.config_from_object(CeleryConfig)


@celery.task(name="tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    """Mock email notification: log the message instead of SMTP."""
    message = (
        f"[email] To: {user_email} — Your task "
        f"'{task_title}' has been completed."
    )
    logger.info(message)
    print(message)
    return {"status": "sent", "to": user_email, "task_title": task_title}
