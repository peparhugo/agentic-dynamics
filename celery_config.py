import os

from celery import Celery


broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
task_routes = {
    "notification_tasks.send_notification_email": {"queue": "notifications"}
}

celery_app = Celery(
    "task_management",
    broker=broker_url,
    backend=result_backend,
    include=["notification_tasks"],
)
celery_app.conf.update(task_routes=task_routes, task_publish_retry=False)
