"""
Celery configuration for async task processing
"""

CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True

CELERY_TASK_ROUTES = {
    "tasks_celery.send_notification_email": {"queue": "notifications"},
}

CELERY_QUEUES = {
    "default": {"exchange": "default", "routing_key": "default"},
    "notifications": {"exchange": "notifications", "routing_key": "notifications"},
}
