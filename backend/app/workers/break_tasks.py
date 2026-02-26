from datetime import date
from .celery_app import celery_app

@celery_app.task(name="assign_break")
def assign_break(advisor_id: int, day_iso: str) -> str:
    """
    Stub. Más adelante: calcula y guarda el break.
    day_iso: 'YYYY-MM-DD' para evitar problemas de serialización.
    """
    # acá luego vas a: leer shift, armar ventana, consultar curva, asignar break, guardar.
    return f"queued assign_break for advisor_id={advisor_id} day={day_iso}"
