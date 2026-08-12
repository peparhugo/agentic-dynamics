import os
from celery import Celery

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "tasks",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
)

celery_app.conf.update(
    task_routes={
        "tasks.send_notification_email": {"queue": "email"},
    },
    task_always_eager=os.environ.get("CELERY_ALWAYS_EAGER", "false").lower() == "true",
)
