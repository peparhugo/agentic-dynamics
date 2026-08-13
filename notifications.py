"""Asynchronous notification tasks."""

import logging

from celery import Celery


celery_app = Celery("task_notifications")
celery_app.config_from_object("celery_config")


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock delivery of a completion notification email."""
    logging.getLogger(__name__).info(
        "Sending completion notification for task %r to %s", task_title, user_email
    )
