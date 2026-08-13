import logging

from celery import Celery


celery_app = Celery("task_notifications")
celery_app.config_from_object("celery_config")


@celery_app.task
def send_notification_email(user_email: str, task_title: str) -> None:
    logging.getLogger(__name__).info(
        "Task '%s' was completed; notification sent to %s", task_title, user_email
    )
