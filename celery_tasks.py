"""
Celery tasks for async operations
"""

import logging
from app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name='send_notification_email')
def send_notification_email(user_email, task_title):
    """
    Send a notification email when a task is completed.
    In a real application, this would send an actual email.
    For now, we mock it by logging.
    """
    if not user_email:
        logger.warning(f"No email provided for task completion: {task_title}")
        return {'status': 'skipped', 'reason': 'no_email'}

    logger.info(f"[EMAIL NOTIFICATION] Task completed: '{task_title}' - Sending email to {user_email}")

    return {
        'status': 'sent',
        'user_email': user_email,
        'task_title': task_title
    }
