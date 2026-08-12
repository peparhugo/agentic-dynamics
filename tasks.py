"""Celery application and notification tasks for the task management API."""

from celery import Celery
import celery_config

celery_app = Celery("task_management")
celery_app.config_from_object(celery_config)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> dict:
    """Send a "task completed" notification email to the task owner.

    This is a mock sender — it prints the email to the console instead of
    delivering it over SMTP.
    """
    print(
        f"[EMAIL] To: {user_email} | Subject: Task completed | "
        f"Your task '{task_title}' is complete."
    )
    return {"email": user_email, "task_title": task_title}
