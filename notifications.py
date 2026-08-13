import logging

from celery import Celery


celery_app = Celery("task_management")
celery_app.config_from_object("celery_config")


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email, task_title):
    logging.getLogger(__name__).info(
        "Notification email sent to %s: task '%s' was completed",
        user_email,
        task_title,
    )
