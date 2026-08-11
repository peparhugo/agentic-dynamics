import os
from celery import Celery

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
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


@celery_app.task
def send_notification_email(user_email: str, task_title: str):
    print(
        f"[EMAIL] Notification sent to {user_email}: "
        f"Your task '{task_title}' has been completed."
    )
    return {"sent": True, "email": user_email, "task_title": task_title}
