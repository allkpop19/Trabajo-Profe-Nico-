"""Reglas rápidas de formulario; SQL vuelve a verificar la integridad."""
import re
from app.db import AppError

PRIORITIES = ("baja", "media", "alta", "critica")
STATUSES = ("abierto", "en_progreso", "resuelto", "cerrado")
LABELS = {"abierto": "Abierto", "en_progreso": "En progreso", "resuelto": "Resuelto", "cerrado": "Cerrado",
          "baja": "Baja", "media": "Media", "alta": "Alta", "critica": "Crítica"}


def clean_text(value, label, minimum=2, maximum=100):
    text = (value or "").strip()
    if not minimum <= len(text) <= maximum:
        raise AppError(f"{label} debe tener entre {minimum} y {maximum} caracteres.")
    return text


def validate_ticket(data):
    result = dict(data)
    result["title"] = clean_text(data.get("title"), "El título", 5, 140)
    result["description"] = clean_text(data.get("description"), "La descripción", 10, 10000)
    result["solution"] = (data.get("solution") or "").strip() or None
    if data.get("priority") not in PRIORITIES or data.get("status", "abierto") not in STATUSES:
        raise AppError("Selecciona una prioridad y un estado válidos.")
    for name in ("requester_id", "specialty_id"):
        try:
            result[name] = int(data.get(name) or 0)
        except (ValueError, TypeError):
            raise AppError("Selecciona un solicitante y una especialidad.") from None
        if result[name] < 1:
            raise AppError("Selecciona un solicitante y una especialidad.")
    if data.get("status") in ("resuelto", "cerrado"):
        result["solution"] = clean_text(result["solution"], "La solución", 10, 10000)
    return result


def validate_email(value):
    email = (value or "").strip().lower()
    if len(email) > 160 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise AppError("Ingresa un correo electrónico válido.")
    return email
