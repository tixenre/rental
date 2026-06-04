"""Scheduler in-process del barrido diario de recordatorios de retiro.

Decisión 2026-06-04 (issue #735): el recordatorio se dispara desde un thread
**dentro del backend que ya corre 24/7**, no como servicio de cron aparte.
Costo extra: $0 (reusa el compute que ya se paga).

**Opt-in por configuración, no por código** (alineado con decisión 2026-05-27 —
los envíos se activan seteando variables, no tocando código): el scheduler solo
arranca si `REMINDERS_ENABLED` está en `1/true/yes`. Apagado por default → en
staging/test no manda nada aunque el código esté deployado. Ops lo prende junto
con la `RESEND_API_KEY` cuando el canal de mail está listo.

**Single-instance:** hoy el backend corre 1 instancia. Si se escala a >1, dos
schedulers dispararían el barrido en paralelo el mismo día → agregar un lock
(ej. `pg_try_advisory_lock`) antes de correr. Aun así no habría mails duplicados:
la red final es el índice único de `emails_log` (ver `jobs/recordatorios.py`).

Mecanismo: un thread daemon que sondea cada `_CHECK_EVERY_S`; una vez por día,
a partir de `REMINDERS_HOUR` (hora AR), corre el barrido y marca la fecha para no
repetir. Simple y sin dependencia nueva (no se agrega APScheduler). Un reinicio
después de la hora puede volver a correrlo, pero el envío es idempotente.
"""

from __future__ import annotations

import logging
import os
import threading
import time

from database import now_ar

logger = logging.getLogger(__name__)

# Hora AR a la que corre el barrido (09:00 → "mañana retirás", a horario humano).
_HORA_CORRIDA = int(os.getenv("REMINDERS_HOUR", "9"))
_CHECK_EVERY_S = 600  # 10 min: granularidad del sondeo


def _enabled() -> bool:
    return os.getenv("REMINDERS_ENABLED", "").strip().lower() in ("1", "true", "yes")


def _loop() -> None:
    # Import perezoso: evita cargar el job (y sus imports de routes) al importar
    # este módulo, y rompe cualquier ciclo de importación al arrancar.
    from jobs.recordatorios import enviar_recordatorios_retiro

    ultima_fecha = None
    while True:
        try:
            ahora = now_ar()
            if ahora.hour >= _HORA_CORRIDA and ahora.date() != ultima_fecha:
                ultima_fecha = ahora.date()
                enviar_recordatorios_retiro()
        except Exception:  # nunca dejar morir el thread por un error puntual
            logger.exception("Falló el barrido de recordatorios de retiro")
        time.sleep(_CHECK_EVERY_S)


def start_scheduler() -> bool:
    """Arranca el thread del scheduler si está habilitado. Devuelve si arrancó.

    Idempotente a nivel proceso: pensado para llamarse una vez al inicio.
    """
    if not _enabled():
        logger.info(
            "Scheduler de recordatorios DESACTIVADO (seteá REMINDERS_ENABLED=1 para activarlo)"
        )
        return False
    threading.Thread(
        target=_loop, name="recordatorios-scheduler", daemon=True
    ).start()
    logger.info(
        "Scheduler de recordatorios ACTIVO (barrido diario ~%02d:00 AR)", _HORA_CORRIDA
    )
    return True
