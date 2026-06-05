"""Resolución de la config del recordatorio de retiro — **fuente única**.

Decide si el recordatorio está prendido, a qué hora corre y con cuántos días de
anticipación. La leen el scheduler in-process (`jobs/scheduler.py`) y el job
(`jobs/recordatorios.py`) — nadie lee estas settings por su cuenta en dos lados.

Precedencia (alineada con `email_from`, decisión 2026-05-27 — la config se
activa por entorno): la **variable de entorno**, si está presente, MANDA
(kill-switch / override de ops); si no, el valor que el admin guardó en
`/admin/settings`; si tampoco, el **default**.

| Concepto    | Env override            | app_settings key            | Default |
| ----------- | ----------------------- | --------------------------- | ------- |
| encendido   | REMINDERS_ENABLED       | recordatorios_enabled       | off     |
| hora (AR)   | REMINDERS_HOUR          | recordatorios_hora          | 9       |
| días antes  | REMINDERS_DIAS_ANTES    | recordatorios_dias_antes    | 1       |
"""
from __future__ import annotations

import logging
import os

from database import get_db

logger = logging.getLogger(__name__)

DEFAULT_HORA = 9
DEFAULT_DIAS_ANTES = 1
MAX_DIAS_ANTES = 14  # tope sano: más que esto no es un "recordatorio de retiro".

_TRUTHY = ("1", "true", "yes")


def _env(name: str) -> str | None:
    """Valor de la env var si está presente y no vacía; si no, None."""
    v = os.getenv(name)
    v = v.strip() if v else ""
    return v or None


def _setting(conn, key: str) -> str:
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key = ?", (key,)
    ).fetchone()
    return (row["value"].strip() if row and row["value"] else "")


def _clamp_int(raw: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(int(raw), hi))
    except (ValueError, TypeError):
        return default


def resolve(conn=None) -> dict:
    """Devuelve `{enabled: bool, hora: int(0-23), dias_antes: int(1-14)}`
    aplicando env > settings > default. `conn=None` abre y cierra su propia
    conexión (uso del scheduler); si se pasa una, no la cierra."""
    propia = conn is None
    if propia:
        conn = get_db()
    try:
        ev = _env("REMINDERS_ENABLED")
        enabled = (
            ev.lower() in _TRUTHY if ev is not None
            else _setting(conn, "recordatorios_enabled").lower() in _TRUTHY
        )
        hora = _clamp_int(
            _env("REMINDERS_HOUR") or _setting(conn, "recordatorios_hora"),
            DEFAULT_HORA, 0, 23,
        )
        dias_antes = _clamp_int(
            _env("REMINDERS_DIAS_ANTES") or _setting(conn, "recordatorios_dias_antes"),
            DEFAULT_DIAS_ANTES, 1, MAX_DIAS_ANTES,
        )
        return {"enabled": enabled, "hora": hora, "dias_antes": dias_antes}
    finally:
        if propia:
            conn.close()
