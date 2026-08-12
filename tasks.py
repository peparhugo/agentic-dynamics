"""
Celery app and asynchronous email notification task.

The Celery instance is configured from celery_config. The
send_notification_email task is dispatched (via .delay) from the API so the
email never blocks the HTTP response. Email sending is mocked with a log/print
so the system runs without a real SMTP server.
"""

from celery import Celery
from celery.utils.log import get_task_logger

import celery_config

logger = get_task_logger(__name__)

celery_app = Celery("tasks")
celery_app.conf.update(
    broker_url=celery_config.BROKER_URL,
    result_backend=celery_config.RESULT_BACKEND,
    task_routes=celery_config.TASK_ROUTES,
)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str):
    """Mock email: log and print the notification that would be sent."""
    message = (
        f"[notification] Task completed: '{task_title}' — "
        f"sending email to {user_email}"
    )
    logger.info(message)
    print(message)
    return {"sent": True, "to": user_email, "task_title": task_title}
