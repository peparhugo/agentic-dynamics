"""Celery configuration for the task management API's async workers.

Broker/backend URLs are read from the environment so the same config works
against a local Redis (docker-compose, dev) or a managed Redis in other
environments, defaulting to a local Redis instance for development.
"""

import os

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True

task_routes = {
    "notifications.send_notification_email": {"queue": "notifications"},
}
