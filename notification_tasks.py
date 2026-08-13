import logging

from celery_config import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(name="notification_tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    logger.info(
        "Sending task completion notification to %s for task %r",
        user_email,
        task_title,
    )
