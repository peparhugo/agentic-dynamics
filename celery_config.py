import os

from celery import Celery


broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
task_routes = {
    "notification_tasks.send_notification_email": {"queue": "notifications"}
}

celery_app = Celery("task_management", include=["notification_tasks"])
celery_app.conf.update(
    broker_url=broker_url,
    result_backend=result_backend,
    task_routes=task_routes,
)
