from celery import Celery

celery_app = Celery('task_manager')
celery_app.config_from_object('celery_config')


@celery_app.task
def send_notification_email(user_email, task_title):
    print(f"[EMAIL] Notification sent to {user_email}: Your task '{task_title}' has been completed.")
    return True
