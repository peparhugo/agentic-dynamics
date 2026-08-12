from celery import Celery

celery_app = Celery(__name__)
celery_app.config_from_object('celery_config')


@celery_app.task
def send_notification_email(user_email: str, task_title: str):
    print(f"NOTIFICATION: Task '{task_title}' completed. Email sent to {user_email}")
