from .celery_app import celery_app
from .break_tasks import assign_break  # noqa: F401


@celery_app.task(name="ping")
def ping():
    return "pong"
