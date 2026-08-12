"""Celery configuration for the task management API.

Uses Redis as both the message broker and result backend. The single
REDIS_URL setting can be overridden via the environment so the broker
and backend can be pointed at the same (or different) Redis instances.
"""

import os

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

broker_url = REDIS_URL
result_backend = REDIS_URL

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

timezone = "UTC"
enable_utc = True

task_routes = {
    "tasks.send_notification_email": {"queue": "notifications"},
}

# Run tasks synchronously in-process (useful for tests / local dev without
# a broker). Enabled via CELERY_TASK_ALWAYS_EAGER=1.
task_always_eager = os.environ.get(
    "CELERY_TASK_ALWAYS_EAGER", "false"
).lower() in ("1", "true", "yes")
