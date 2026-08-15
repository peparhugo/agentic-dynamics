"""Celery configuration and asynchronous notification tasks."""

import logging
import os

from celery import Celery

logger = logging.getLogger(__name__)

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery("task_management")

celery_app.conf.update(
    broker_url=BROKER_URL,
    result_backend=RESULT_BACKEND,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_routes={
        "celery_config.send_notification_email": {"queue": "notifications"},
    },
)


@celery_app.task(name="celery_config.send_notification_email")
def send_notification_email(user_email, task_title):
    """Mock email sending: log instead of contacting an SMTP server."""
    logger.info(
        "Sending notification email to %s for task '%s'", user_email, task_title
    )
    return {"user_email": user_email, "task_title": task_title}
