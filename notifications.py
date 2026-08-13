from celery_config import celery_app


@celery_app.task(name="notifications.send_notification_email")
def send_notification_email(user_email, task_title):
    print(f"Notification email sent to {user_email}: task '{task_title}' completed")
