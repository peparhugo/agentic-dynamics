from celery import Celery


celery_app = Celery("task_management")
celery_app.config_from_object("celery_config")


@celery_app.task
def send_notification_email(user_email, task_title):
    print(f"Notification email sent to {user_email}: task '{task_title}' completed")
