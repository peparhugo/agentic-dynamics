import os
from celery import Celery

class CeleryConfig:
    broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    task_serializer = 'json'
    accept_content = ['json']
    result_serializer = 'json'
    timezone = 'UTC'
    enable_utc = True
    task_track_started = True
    task_time_limit = 30 * 60
    broker_connection_retry_on_startup = True

def make_celery(app=None):
    """Create and configure Celery instance"""
    celery = Celery(
        app.import_name if app else 'app',
        backend=CeleryConfig.result_backend,
        broker=CeleryConfig.broker_url
    )

    if app:
        celery.conf.update(app.config)

    celery.config_from_object(CeleryConfig)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            if app:
                with app.app_context():
                    return self.run(*args, **kwargs)
            return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
