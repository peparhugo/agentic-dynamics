import os

from celery import Celery

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
)

celery_app = Celery(
    "task_api",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_routes={
        "send_notification_email": {"queue": "notifications"},
    },
    task_always_eager=os.environ.get("CELERY_TASK_ALWAYS_EAGER", "false").lower()
    in ("1", "true", "yes"),
)


@celery_app.task(name="send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    print(
        f"[notifications] Email sent to {user_email}: "
        f"task '{task_title}' has been completed"
    )
    return f"email sent to {user_email} for task '{task_title}'"
