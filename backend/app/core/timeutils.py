from __future__ import annotations

def hhmm_to_min(hhmm: str) -> int:
    """
    Convierte 'HH:MM' a minutos desde 00:00.
    Acepta HH 00-23 y MM 00-59.
    """
    if not isinstance(hhmm, str) or ":" not in hhmm:
        raise ValueError("Time must be in 'HH:MM' format")

    parts = hhmm.split(":")
    if len(parts) != 2:
        raise ValueError("Time must be in 'HH:MM' format")

    hh = int(parts[0])
    mm = int(parts[1])

    if not (0 <= hh <= 23):
        raise ValueError("Hour must be 00..23")
    if not (0 <= mm <= 59):
        raise ValueError("Minute must be 00..59")

    return hh * 60 + mm


def min_to_hhmm(minutes: int) -> str:
    """
    Convierte minutos desde 00:00 a 'HH:MM'.
    """
    if not isinstance(minutes, int):
        raise ValueError("minutes must be int")
    if minutes < 0 or minutes > 1440:
        raise ValueError("minutes must be 0..1440")

    hh = minutes // 60
    mm = minutes % 60
    return f"{hh:02d}:{mm:02d}"


def slot_index_to_hhmm(slot_index: int) -> str:
    """
    slot 0..47 -> 'HH:MM' donde cada slot son 30 minutos.
    """
    if slot_index < 0 or slot_index > 47:
        raise ValueError("slot_index must be 0..47")
    return min_to_hhmm(slot_index * 30)
