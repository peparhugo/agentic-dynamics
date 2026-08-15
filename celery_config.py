"""
Celery configuration for the task management API's async notification system.

Broker/backend default to a local Redis instance; override via env vars when
deploying against a different Redis host (or a managed broker).
"""

import os

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

task_routes = {
    "notifications.send_notification_email": {"queue": "notifications"},
}

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True
