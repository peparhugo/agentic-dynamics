from celery_config import celery_app


@celery_app.task
def send_notification_email(user_email, task_title):
    print(
        f"[EMAIL NOTIFICATION] To: {user_email} | "
        f"Subject: Task Completed | "
        f"Body: Your task '{task_title}' has been completed."
    )
