import logging
import os
from celery import Celery

logger = logging.getLogger(__name__)

celery_app = Celery(
    "tasks",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "celery_config.send_notification_email": {"queue": "email"},
    },
)


@celery_app.task
def send_notification_email(user_email: str, task_title: str):
    logger.info(
        "Sending notification email to %s for task '%s'", user_email, task_title
    )
    print(
        f"[NOTIFICATION] Email sent to {user_email}: "
        f"Your task '{task_title}' has been completed."
    )
    return f"Notification sent to {user_email} for task '{task_title}'"
