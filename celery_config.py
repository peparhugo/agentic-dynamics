"""
Celery configuration for the task management API.

Uses Redis as the message broker and result backend. Notification emails are
routed to a dedicated queue.
"""

broker_url = "redis://localhost:6379/0"
result_backend = "redis://localhost:6379/0"

task_routes = {
    "celery_app.send_notification_email": {"queue": "email"},
}

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

timezone = "UTC"
enable_utc = True
