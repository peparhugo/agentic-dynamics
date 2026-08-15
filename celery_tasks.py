import logging
from celery_config import make_celery

logger = logging.getLogger(__name__)

celery = make_celery()

@celery.task(name='send_notification_email')
def send_notification_email(user_email, task_title):
    """
    Send email notification to user when task is completed.
    Mock implementation logs and prints the email.
    """
    try:
        message = f"Task completed: {task_title}"
        logger.info(f"Sending email to {user_email}: {message}")
        print(f"[EMAIL] To: {user_email}")
        print(f"[EMAIL] Subject: Task Completed Notification")
        print(f"[EMAIL] Body: Your task '{task_title}' has been marked as completed.")
        return {'status': 'sent', 'email': user_email, 'task': task_title}
    except Exception as e:
        logger.error(f"Failed to send email to {user_email}: {str(e)}")
        raise
