"""Celery configuration for async task processing."""
import os


class Config:
    # Broker and backend configuration
    broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    # Task configuration
    task_serializer = "json"
    accept_content = ["json"]
    result_serializer = "json"
    timezone = "UTC"
    enable_utc = True

    # Task routing
    task_routes = {
        "tasks.send_notification_email": {"queue": "notifications"},
    }

    # Queue configuration
    task_queues = {
        "notifications": {
            "exchange": "notifications",
            "routing_key": "notification.#",
        }
    }
