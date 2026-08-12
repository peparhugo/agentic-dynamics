from celery import Celery
import celery_config

celery_app = Celery("tasks")
celery_app.config_from_object(celery_config)


@celery_app.task
def send_notification_email(user_email, task_title):
    print(f"[NOTIFICATION] Sending email to {user_email}: Your task '{task_title}' has been completed.")
    return f"Email sent to {user_email} for task '{task_title}'"
