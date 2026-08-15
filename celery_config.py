import os

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_config = {
    "broker_url": BROKER_URL,
    "result_backend": RESULT_BACKEND,
    "task_routes": {
        "tasks.send_notification_email": {"queue": "notifications"},
    },
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "timezone": "UTC",
    "enable_utc": True,
    "task_track_started": True,
}
