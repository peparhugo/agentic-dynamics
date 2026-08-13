"""
Celery configuration for async task processing.
"""

import os


class CeleryConfig:
    """Celery configuration settings."""
    broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    task_serializer = "json"
    accept_content = ["json"]
    result_serializer = "json"
    timezone = "UTC"
    enable_utc = True
    task_routes = {
        "celery_tasks.send_notification_email": {"queue": "notifications"}
    }
