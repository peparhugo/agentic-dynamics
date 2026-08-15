"""Celery configuration for async tasks."""

broker_url = "redis://localhost:6379/0"
result_backend = "redis://localhost:6379/0"
task_serializer = "json"
accept_content = ["json"]
result_serializer = "json"
timezone = "UTC"
enable_utc = True

task_routes = {
    "celery_tasks.send_notification_email": {"queue": "notifications"},
}
