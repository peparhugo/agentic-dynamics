from celery_config import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(name='tasks.send_notification_email')
def send_notification_email(user_email, task_title):
    """
    Async task to send notification email when a task is completed.
    For now, this is a mock implementation that logs the notification.
    """
    if user_email:
        logger.info(f'Sending notification email to {user_email} for task: {task_title}')
        print(f'[NOTIFICATION] Email sent to {user_email}: Task "{task_title}" has been completed!')
    else:
        logger.warning('Cannot send notification email: user email not available')
        print(f'[NOTIFICATION] Cannot send email for task "{task_title}": user email not available')
