"""Celery application instance for the task management API."""

import celery_config
from celery import Celery

celery_app = Celery("task_management")
celery_app.config_from_object(celery_config)
