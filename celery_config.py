"""Celery configuration: broker, result backend, and task routing."""

import os

from celery import Celery

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

task_routes = {
    "tasks.send_notification_email": {"queue": "notifications"},
}

# Run tasks eagerly when no broker is available (e.g. in tests/CI). In a real
# deployment set CELERY_TASK_ALWAYS_EAGER=false to dispatch asynchronously via
# Redis.
task_always_eager = (
    os.environ.get("CELERY_TASK_ALWAYS_EAGER", "true").lower()
    in ("1", "true", "yes", "on")
)

celery_app = Celery(
    "task_manager",
    broker=broker_url,
    backend=result_backend,
)

celery_app.conf.update(
    broker_url=broker_url,
    result_backend=result_backend,
    task_routes=task_routes,
    task_always_eager=task_always_eager,
    task_ignore_result=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
