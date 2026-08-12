"""
Celery configuration for the task management API.

Broker/backend settings are read from environment variables so the
application can run against a local Redis or a managed service, and
tests can switch to an eager/in-memory mode.
"""

import os

# Redis message broker used to queue notification emails.
broker_url = os.environ.get(
    "CELERY_BROKER_URL", "redis://localhost:6379/0"
)

# Where task results are stored once executed.
result_backend = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"
)

# Route the notification task to a dedicated "email" queue so it can be
# scaled/handled independently from the rest of the workers.
task_routes = {
    "celery_app.send_notification_email": {"queue": "email"},
}

# Enable eager execution (task runs in-process, synchronously) when the
# broker is unavailable, e.g. in tests or local development.
task_always_eager = os.environ.get(
    "CELERY_TASK_ALWAYS_EAGER", "false"
).lower() in ("1", "true", "yes")

# Propagate task exceptions when running eagerly so failures surface.
task_eager_propagates = True

# Serialize task arguments as JSON for broker interop.
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
