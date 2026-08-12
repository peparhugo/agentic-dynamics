import logging

from celery_config import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock email delivery; a worker can replace this implementation later."""
    logger.info("Sending task completion email to %s for %s", user_email, task_title)
    print(f"Task completed notification for {user_email}: {task_title}")
