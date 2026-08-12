from celery import Celery

from celery_config import broker_url, result_backend

celery = Celery("tasks", broker=broker_url, backend=result_backend)
celery.config_from_object("celery_config")


@celery.task(name="celery_app.send_notification_email")
def send_notification_email(user_email, task_title):
    print(f"[EMAIL] Sending completion notification to {user_email}: '{task_title}'")
    return f"Notification sent to {user_email} for task '{task_title}'"
