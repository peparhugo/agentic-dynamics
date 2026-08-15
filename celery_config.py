"""
Celery configuration for task queue.
"""

class CeleryConfig:
    broker_url = "redis://localhost:6379/0"
    result_backend = "redis://localhost:6379/1"
    task_serializer = "json"
    accept_content = ["json"]
    result_serializer = "json"
    timezone = "UTC"
    enable_utc = True

    task_routes = {
        "tasks.send_notification_email": {"queue": "emails"},
    }

    task_track_started = True
