"""Celery application instance for the task management API.

Broker/backend/routing configuration lives in celery_config.py.
"""

from celery import Celery

celery_app = Celery("task_manager")
celery_app.config_from_object("celery_config")
