import os
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "task_notifications",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_routes={
        "tasks.send_notification_email": {"queue": "email"},
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
