"""Celery configuration: broker URL, result backend, and task routing.

Redis is used as both the message broker and the result backend. URLs are
overridable via environment variables so tests/deployments can point at a
different Redis instance (or database index) without code changes.
"""

import os

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

task_routes = {
    "tasks.send_notification_email": {"queue": "notifications"},
}

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True
