"""Visibilidad del estado de las migraciones Alembic, capturado en el arranque.

**Por qué existe.** El arranque corre `alembic upgrade head` en un thread de
background y, si falla, lo loguea con `logger.error` y la app sigue arrancando
(decisión deliberada: una migración con bug no debe tumbar el deploy). El efecto
colateral es que una migración que aborta —por ejemplo una falla
*data-dependiente*, como `f5b8d2e4a9c1` que corta si hay slugs duplicados en
`equipos`— deja la BD **trabada en una revisión vieja en silencio**: ninguna
migración posterior se aplica y nadie se entera salvo que lea los logs de
Railway.

Este módulo hace ese *drift* **visible**: guarda en memoria el resultado del
último intento de upgrade (revisión aplicada vs head esperado, y el error si
hubo) y lo expone vía `/health` y `/health/migrations`. Es la fuente única del
estado de migraciones para la app en runtime — no recrear este chequeo ad-hoc
en otro lado.

Liviano a propósito: estado en memoria de proceso (no toca la BD salvo para leer
`alembic_version`), thread-safe, sin dependencias de framework.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# Estado del último chequeo. `checked=False` hasta que el arranque corre el
# upgrade (en el ínterin /health reporta "desconocido", no "roto").
_state: dict[str, Any] = {
    "checked": False,    # ¿ya corrió el chequeo de migraciones en este proceso?
    "ok": None,          # True si la BD está en el head y sin error
    "current": None,     # revisión aplicada en la BD (de alembic_version)
    "head": None,        # head esperado del repo (de las migraciones en disco)
    "error": None,       # str de la excepción si el upgrade falló (sino None)
}


def _head_revision(cfg) -> Optional[str]:
    """Head esperado según las migraciones en disco. Tolera multiple-heads
    (devuelve los heads unidos por coma) para no romper la visibilidad."""
    from alembic.script import ScriptDirectory

    heads = ScriptDirectory.from_config(cfg).get_heads()
    if not heads:
        return None
    if len(heads) == 1:
        return heads[0]
    return ",".join(sorted(heads))


def _current_revision() -> Optional[str]:
    """Revisión aplicada según `alembic_version` en la BD. Devuelve None si la
    tabla no existe todavía (BD pre-Alembic) — eso no es drift, es bootstrap."""
    from database import get_db

    conn = get_db()
    try:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        return row[0] if row else None
    except Exception:
        # La tabla puede no existir aún; el rollback lo hace conn.close().
        return None
    finally:
        conn.close()


def record_success(cfg) -> None:
    """Registrar el resultado de un `upgrade head` que terminó sin excepción.

    Aun sin excepción, compara aplicado vs head como red de seguridad: si por
    algún motivo no quedó en el head, lo deja marcado como NO-ok y avisa fuerte.
    """
    head = _head_revision(cfg)
    current = _current_revision()
    ok = current is not None and current == head
    with _lock:
        _state.update(checked=True, ok=ok, current=current, head=head, error=None)
    if ok:
        logger.info("Migraciones Alembic al día (revisión %s)", current)
    else:
        logger.error(
            "DRIFT DE MIGRACIONES: la BD está en %r pero el head del repo es %r. "
            "Hay migraciones sin aplicar — ver runbook en docs/RUNBOOK_MIGRACIONES.md.",
            current, head,
        )


def record_failure(error: BaseException, cfg=None) -> None:
    """Registrar que el `upgrade head` tiró una excepción → la BD quedó trabada
    en la revisión actual. Captura el estado para exponerlo en /health."""
    current = _current_revision()
    head = None
    if cfg is not None:
        try:
            head = _head_revision(cfg)
        except Exception:
            head = None
    with _lock:
        _state.update(checked=True, ok=False, current=current, head=head, error=str(error))


def get_status() -> dict[str, Any]:
    """Snapshot del estado actual (copia, para no exponer el dict mutable)."""
    with _lock:
        return dict(_state)
