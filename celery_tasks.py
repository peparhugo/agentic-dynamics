"""Celery application and notification tasks for the task management API."""

from celery import Celery

from celery_config import (
    CELERY_ACCEPT_CONTENT,
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CELERY_RESULT_SERIALIZER,
    CELERY_TASK_ROUTES,
    CELERY_TASK_SERIALIZER,
    CELERY_TIMEZONE,
    CELERY_TASK_TRACK_STARTED,
)

celery_app = Celery(
    "tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_routes=CELERY_TASK_ROUTES,
    task_serializer=CELERY_TASK_SERIALIZER,
    accept_content=CELERY_ACCEPT_CONTENT,
    result_serializer=CELERY_RESULT_SERIALIZER,
    timezone=CELERY_TIMEZONE,
    task_track_started=CELERY_TASK_TRACK_STARTED,
)


@celery_app.task(name="send_notification_email")
def send_notification_email(user_email: str, task_title: str):
    """Send a notification email to a task owner (mock implementation)."""
    print(f"[EMAIL] To: {user_email} — Task '{task_title}' completed")
    return {"to": user_email, "subject": f"Task completed: {task_title}"}
