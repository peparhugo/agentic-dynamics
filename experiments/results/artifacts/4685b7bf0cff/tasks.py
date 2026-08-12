"""Background tasks used by the task management API."""

import logging

from celery_config import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> None:
    """Send a completion notification (mocked with a log message)."""
    logger.info("Notification email sent to %s for completed task %s", user_email, task_title)
