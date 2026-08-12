import logging
from celery_config import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def send_notification_email(user_email: str, task_title: str) -> str:
    msg = f"[EMAIL NOTIFICATION] To: {user_email}, Task '{task_title}' has been completed"
    print(msg)
    logger.info(msg)
    return msg
