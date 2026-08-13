"""
Celery configuration for async email notifications.
"""

import os

# Broker configuration (Redis)
broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Task configuration
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'UTC'
enable_utc = True

# Task routes for organizing tasks
task_routes = {
    'celery_tasks.send_notification_email': {'queue': 'notifications'},
}
