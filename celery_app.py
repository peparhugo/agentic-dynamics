"""
Celery application and asynchronous notification tasks.

The notification email task is dispatched from the API via
``send_notification_email.delay(...)`` so the HTTP response is never
blocked by the (mock) email delivery.
"""

from celery import Celery

import celery_config

celery_app = Celery(
    "task_manager", config_source="celery_config"
)


@celery_app.task
def send_notification_email(user_email, task_title):
    """Asynchronously notify the task owner that their task is done.

    Email delivery is mocked for now: the notification is written to
    the console / application logs. Swap this body for a real SMTP /
    provider integration without touching the API layer.
    """
    print(
        f"[notification] Sending email to {user_email}: "
        f'task "{task_title}" is completed'
    )
    return {"user_email": user_email, "task_title": task_title}
