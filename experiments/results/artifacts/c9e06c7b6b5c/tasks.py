from celery_config import celery_app


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> None:
    """Mock the notification email; workers can replace this implementation later."""
    print(f"Notification email sent to {user_email}: task '{task_title}' is completed")
