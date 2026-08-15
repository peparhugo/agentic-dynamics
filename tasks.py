from celery import Celery

from celery_config import celery_config

celery_app = Celery("task_manager")
celery_app.conf.update(celery_config)


@celery_app.task(name="tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    print(
        f"[notification] sending email to {user_email}: "
        f"your task '{task_title}' is completed",
        flush=True,
    )
    return {"sent": True, "to": user_email, "task_title": task_title}
