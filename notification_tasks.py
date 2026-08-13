import logging

from celery import Celery


celery_app = Celery("task_management")
celery_app.config_from_object("celery_config")


@celery_app.task(name="notification_tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    logging.getLogger(__name__).info(
        "Sending task completion notification to %s for %s",
        user_email,
        task_title,
    )
