import logging

from celery import Celery


celery_app = Celery("task_management_api")
celery_app.config_from_object("celery_config")

logger = logging.getLogger(__name__)


@celery_app.task(name="notification_tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    logger.info(
        "Notification email sent to %s: task '%s' was completed",
        user_email,
        task_title,
    )
