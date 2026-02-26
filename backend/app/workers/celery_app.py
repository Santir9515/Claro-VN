import os
from celery import Celery

# Redis para broker y backend (result store)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "wfm_breaks",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# Config base
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # evita warning futuro de Celery 6 sobre retries
    broker_connection_retry_on_startup=True,
)

# Opción 1 (recomendada): autodiscover de tasks en el paquete "app.workers"
# Busca módulos llamados "tasks.py" dentro de los paquetes listados.
celery_app.autodiscover_tasks(["app.workers"])

# Si preferís ser explícito en vez de autodiscover, comentá la línea anterior
# y descomentá esta:
# from app.workers import tasks  # noqa: F401
