"""Celery configuration: broker, result backend, and task routing."""

broker_url = "redis://localhost:6379/0"
result_backend = "redis://localhost:6379/0"

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True

task_routes = {
    "tasks.send_notification_email": {"queue": "notifications"},
}
