"""
Celery application for the task management API.

Defines send_notification_email, a background task that notifies a task's
owner by email when their task is marked completed. Sending is mocked (it
logs to the console) since no real email provider is wired up.
"""

import logging

from celery import Celery

import celery_config

logger = logging.getLogger(__name__)

celery_app = Celery("task_api")
celery_app.config_from_object(celery_config)


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email, task_title):
    message = f"[email] To: {user_email} | Your task '{task_title}' is now completed."
    print(message)
    logger.info(message)
    return {"user_email": user_email, "task_title": task_title, "sent": True}
