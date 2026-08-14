"""Celery configuration for the task management API."""

import os

broker_url = os.environ.get(
    "CELERY_BROKER_URL", "redis://localhost:6379/0"
)
result_backend = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
)

task_routes = {
    "tasks.send_notification_email": {"queue": "email"},
}

task_default_queue = "default"

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True
