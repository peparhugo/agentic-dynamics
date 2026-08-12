from celery import Celery

celery_app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

celery_app.conf.update(
    task_routes={
        "celery_config.send_notification_email": {"queue": "email"},
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)


@celery_app.task(name="celery_config.send_notification_email")
def send_notification_email(user_email, task_title):
    print(f"[EMAIL NOTIFICATION] To: {user_email} | Task completed: {task_title}")
    return f"Email sent to {user_email} for task '{task_title}'"
