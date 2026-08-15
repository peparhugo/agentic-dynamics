"""
Celery configuration for the task management API.

Broker and result backend default to a local Redis server but can be
overridden via environment variables (useful for development/production).
"""

import os


class CeleryConfig:
    broker_url = os.environ.get(
        "CELERY_BROKER_URL", "redis://localhost:6379/0"
    )
    result_backend = os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"
    )
    task_routes = {
        "tasks.send_notification_email": {"queue": "email"},
    }
    task_serializer = "json"
    result_serializer = "json"
    accept_content = ["json"]
    timezone = "UTC"
    enable_utc = True
    task_always_eager = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "0") == "1"
    task_eager_propagates = True
