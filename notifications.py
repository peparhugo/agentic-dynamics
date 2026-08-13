"""Asynchronous task notification jobs."""

import logging

from celery import Celery


celery_app = Celery("task_notifications")
celery_app.config_from_object("celery_config")


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock delivery until a transactional email provider is configured."""
    logging.getLogger(__name__).info(
        "Sending task completion email to %s for task %s", user_email, task_title
    )
