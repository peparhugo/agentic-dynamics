import os
from celery import Celery

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery("tasks", broker=BROKER_URL, backend=RESULT_BACKEND)

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


@celery_app.task
def send_notification_email(user_email: str, task_title: str) -> str:
    print(f"[EMAIL] To: {user_email} | Subject: Task '{task_title}' has been completed.")
    return f"Notification sent to {user_email} for task '{task_title}'"
