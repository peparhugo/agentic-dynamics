from celery import Celery
import os

celery = Celery(__name__)
celery.config_from_object('celery_config')


@celery.task(name='celery_tasks.send_notification_email')
def send_notification_email(user_email, task_title):
    """
    Send notification email to user when task is completed.
    In production, this would integrate with an email service.
    For now, we log the notification.
    """
    message = f"[NOTIFICATION] Task '{task_title}' completed for {user_email}"
    print(message)
    return message
