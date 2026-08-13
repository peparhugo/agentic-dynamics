# Async Email Notification System

## Overview

The task management API now includes an async email notification system using Celery and Redis. When a task's status changes to 'completed', a notification email is sent to the task owner asynchronously without blocking the API response.

## Architecture

### Components

1. **Celery Task (`tasks_celery.py`)**
   - Defines the `send_notification_email` Celery task
   - Sends email notifications asynchronously
   - Email sending is currently mocked (prints to console/logs)

2. **Configuration (`celery_config.py`)**
   - Redis broker URL: `redis://localhost:6379/0`
   - Redis result backend: `redis://localhost:6379/1`
   - Task routes configured for notifications queue

3. **API Integration (`task_app.py`)**
   - Users can register with an optional email address
   - When a task status changes to 'completed', the notification task is queued
   - Non-blocking: Email sending happens asynchronously

## Setup & Running

### Prerequisites

Install dependencies:
```bash
pip install -r requirements.txt
```

### Start Redis

```bash
redis-server
```

### Start Celery Worker

```bash
celery -A tasks_celery worker --loglevel=info
```

### Run the Flask App

```bash
python3 task_app.py
```

## API Endpoints

### Register User with Email
```bash
POST /auth/register
{
  "username": "john",
  "password": "securepass123",
  "email": "john@example.com"
}
```

### Create a Task
```bash
POST /tasks
Authorization: Bearer <token>
{
  "title": "Buy groceries"
}
```

### Update Task to Completed
```bash
PUT /tasks/{task_id}
Authorization: Bearer <token>
{
  "status": "completed"
}
```

When this request completes, a Celery task will be queued to send a notification email to the task owner.

## Notification Behavior

- **Triggered:** When task status changes to 'completed' AND wasn't already 'completed'
- **Only Sent:** If the user has an email address on record
- **Non-blocking:** The API response is returned immediately; email is sent asynchronously
- **Failure Handling:** If Celery is not available, a warning is logged but the API continues to function normally

## Mock Email Implementation

Currently, email sending is mocked for testing purposes. In the `tasks_celery.py` file:

```python
@app.task(name="tasks_celery.send_notification_email")
def send_notification_email(user_email: str, task_title: str) -> str:
    message = f"📧 Email notification sent to {user_email}: Task '{task_title}' has been completed."
    print(message)
    logger.info(message)
    return message
```

To integrate a real email service (e.g., SMTP, SendGrid), replace this implementation with actual email sending logic.

## Testing

Run tests with:
```bash
pytest test_task_app.py -v
```

Test coverage includes:
- Notification triggered when task status changes to 'completed'
- Notification not sent without user email
- Notification not sent for non-completed status changes
- Notification not re-sent if task was already completed
- User registration with/without email
