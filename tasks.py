"""
Celery tasks for async operations.
"""

from celery import Celery
from celery_config import (
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CELERY_TASK_SERIALIZER,
    CELERY_RESULT_SERIALIZER,
    CELERY_ACCEPT_CONTENT,
    CELERY_TIMEZONE,
    CELERY_TASK_ROUTES,
)

celery = Celery(__name__)
celery.conf.broker_url = CELERY_BROKER_URL
celery.conf.result_backend = CELERY_RESULT_BACKEND
celery.conf.task_serializer = CELERY_TASK_SERIALIZER
celery.conf.result_serializer = CELERY_RESULT_SERIALIZER
celery.conf.accept_content = CELERY_ACCEPT_CONTENT
celery.conf.timezone = CELERY_TIMEZONE
celery.conf.task_routes = CELERY_TASK_ROUTES


@celery.task
def send_notification_email(user_email, task_title):
    """
    Send a notification email to the task owner.
    Mock implementation that logs to console.
    """
    print(f"[NOTIFICATION] Email sent to {user_email}: Task '{task_title}' has been completed!")
    return f"Notification sent to {user_email}"
