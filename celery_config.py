"""
Celery configuration for the task management API.

Uses Redis as the message broker and result backend. Task routes keep
notification emails on a dedicated "notifications" queue.
"""

import os

BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

TASK_ROUTES = {
    "tasks.send_notification_email": {"queue": "notifications"},
}
