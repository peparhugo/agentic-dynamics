"""
Celery configuration for the Task Management API
"""

import os

broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

task_serializer = "json"
accept_content = ["json"]
result_serializer = "json"
timezone = "UTC"
enable_utc = True

task_routes = {
    "tasks_celery.send_notification_email": {"queue": "notifications"},
}

task_track_started = True
task_time_limit = 30 * 60
task_soft_time_limit = 25 * 60
