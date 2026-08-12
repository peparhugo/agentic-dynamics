"""
Celery configuration for the task management API.

Uses Redis as both the message broker and the result backend. Email
notification tasks are routed to a dedicated "emails" queue so they can be
tuned independently from the rest of the workload.
"""

import os

BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", BROKER_URL)

TASK_SERIALIZER = "json"
RESULT_SERIALIZER = "json"
ACCEPT_CONTENT = ["json"]
TIMEZONE = "UTC"
ENABLE_UTC = True

TASK_ROUTES = {
    "notifications.send_notification_email": {"queue": "emails"},
}

# When enabled, Celery executes tasks synchronously in-process instead of
# dispatching to a worker. Used to keep the test-suite dependency-free.
TASK_ALWAYS_EAGER = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "0") == "1"
