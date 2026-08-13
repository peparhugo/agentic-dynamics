from celery import Celery


celery_app = Celery("task_notifications")
celery_app.config_from_object("celery_config")


@celery_app.task(name="notification_tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> None:
    print(f"Notification email to {user_email}: task '{task_title}' was completed")
