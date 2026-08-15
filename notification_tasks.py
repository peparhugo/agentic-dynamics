import logging

from celery_config import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(name="notification_tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock delivery until a real email provider is configured."""
    logger.info(
        "Notification email to %s: task '%s' has been completed",
        user_email,
        task_title,
    )
