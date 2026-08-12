from celery import Celery
from celery_config import broker_url, result_backend, task_serializer, accept_content, timezone, enable_utc, task_routes

celery_app = Celery("tasks")
celery_app.conf.update(
    broker_url=broker_url,
    result_backend=result_backend,
    task_serializer=task_serializer,
    result_serializer=task_serializer,
    accept_content=accept_content,
    timezone=timezone,
    enable_utc=enable_utc,
    task_routes=task_routes,
    task_always_eager=False,
)


@celery_app.task(name="celery_tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    print(
        f"[EMAIL NOTIFICATION] Task '{task_title}' completed."
        f" Email sent to {user_email}"
    )
    return {"status": "sent", "to": user_email, "task": task_title}
