"""Celery application used by the task management API."""

from celery import Celery


celery_app = Celery("task_management")
celery_app.config_from_object("celery_config")
