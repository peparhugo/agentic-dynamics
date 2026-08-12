"""
Celery application for the task management API.

Defines the asynchronous task used to notify task owners by email when one of
their tasks is marked as completed. The email sending itself is mocked (printed
to the console) — swap in a real mail client to send actual emails.
"""

from celery import Celery

from celery_config import (
    ACCEPT_CONTENT,
    BROKER_URL,
    ENABLE_UTC,
    RESULT_BACKEND,
    RESULT_SERIALIZER,
    TASK_ALWAYS_EAGER,
    TASK_ROUTES,
    TASK_SERIALIZER,
    TIMEZONE,
)

celery_app = Celery("task_management")
celery_app.conf.update(
    broker_url=BROKER_URL,
    result_backend=RESULT_BACKEND,
    task_serializer=TASK_SERIALIZER,
    result_serializer=RESULT_SERIALIZER,
    accept_content=ACCEPT_CONTENT,
    timezone=TIMEZONE,
    enable_utc=ENABLE_UTC,
    task_routes=TASK_ROUTES,
    task_always_eager=TASK_ALWAYS_EAGER,
)


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    """Send a completion notification email (mock implementation)."""
    message = (
        f"To: {user_email} | Subject: Task completed | "
        f"Body: Your task '{task_title}' has been marked as completed."
    )
    print(f"[mock email] {message}")
    return message
