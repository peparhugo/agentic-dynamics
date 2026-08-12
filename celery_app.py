"""
Celery application instance for the Task Management API.

Import ``celery_app`` from this module wherever a task needs to be defined
or a worker needs to be started:

    celery -A celery_app worker --loglevel=info
"""

from celery import Celery

import celery_config

celery_app = Celery("task_management_api")
celery_app.config_from_object(celery_config)
