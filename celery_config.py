"""
Celery configuration for the task management API's async notification system.

Broker/backend default to a local Redis instance but can be overridden via
environment variables for different deployments (e.g. docker-compose, CI).
"""

import os

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True

task_routes = {
    "send_notification_email": {"queue": "notifications"},
}

# When true, .delay()/.apply_async() run the task synchronously in-process
# instead of publishing to the broker. Useful for tests/environments without
# a running Redis instance.
task_always_eager = os.environ.get("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
