"""Background notification tasks."""

import logging

from celery import Celery

import celery_config


celery_app = Celery("task_management_api")
celery_app.config_from_object(celery_config)


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email, task_title):
    """Send a completion notification (mocked by logging for now)."""
    logging.getLogger(__name__).info(
        "Task completed notification for %s: %s", user_email, task_title
    )
