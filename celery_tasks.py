"""Background tasks used by the task management API."""

from celery import Celery

from celery_config import broker_url, result_backend, task_routes


celery_app = Celery("task_management")
celery_app.conf.update(
    broker_url=broker_url,
    result_backend=result_backend,
    task_routes=task_routes,
)


@celery_app.task(name="celery_tasks.send_notification_email")
def send_notification_email(user_email, task_title):
    """Mock sending an email to the task owner."""
    print(f"Notification email to {user_email}: task completed: {task_title}")
