import logging

from celery import Celery

celery_app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)

celery_app.conf.update(
    task_routes={
        "celery_config.send_notification_email": {"queue": "email"},
    },
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="send_notification_email")
def send_notification_email(user_email, task_title):
    message = (
        f"[EMAIL NOTIFICATION] To: {user_email} | "
        f"Task '{task_title}' has been completed."
    )
    logger.info(message)
    print(message)
    return message
