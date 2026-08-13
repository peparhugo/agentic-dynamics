"""
Celery application instance for the task management API.

Import ``celery_app`` and register tasks against it (see tasks.py).
"""

from celery import Celery

import celery_config

celery_app = Celery("task_manager")
celery_app.config_from_object(celery_config)
