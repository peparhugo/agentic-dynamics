from celery import Celery

celery_app = Celery("tasks")

celery_app.conf.update(
    broker_url="redis://localhost:6379/0",
    result_backend="redis://localhost:6379/0",
    task_routes={
        "celery_config.send_notification_email": {"queue": "email"},
    },
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task
def send_notification_email(user_email, task_title):
    print(f"[EMAIL] To: {user_email} | Task '{task_title}' has been completed.")
    return f"Notification sent to {user_email} for task '{task_title}'"
