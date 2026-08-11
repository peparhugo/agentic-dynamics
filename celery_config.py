import logging

from celery import Celery

logger = logging.getLogger(__name__)

celery_app = Celery("tasks")

celery_app.config_from_object(
    {
        "broker_url": "redis://localhost:6379/0",
        "result_backend": "redis://localhost:6379/0",
        "task_routes": {
            "tasks.send_notification_email": {"queue": "email"},
        },
        "broker_connection_retry_on_startup": True,
    }
)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    logger.info(
        "Sending notification email to %s for task: %s", user_email, task_title
    )
    return f"Email sent to {user_email} for task '{task_title}'"
