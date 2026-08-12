"""
Celery configuration for the Task Management API.

Uses Redis as the message broker and result backend. The notification email
task is routed to a dedicated "email" queue.
"""

import os

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"
)

CELERY_TASK_ROUTES = {
    "send_notification_email": {"queue": "email"},
}

CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
