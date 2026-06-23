"""Registro persistente de errores del servidor (#280 follow-up).

log_server_error() es best-effort: abre su propia conexión para no quedar
atrapada en una transacción que ya falló. Nunca lanza; si ella misma falla
solo lo loguea y sigue.
"""

import logging
import traceback
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_LEN = 8000


def log_server_error(route: str, exc: Exception, request_id: Optional[str] = None) -> None:
    """Persiste el error en `server_errors`. Best-effort: no lanza."""
    try:
        from database import get_db

        tb = traceback.format_exc()
        error_type = type(exc).__name__
        message = str(exc)[:_MAX_LEN]
        tb_truncated = tb[:_MAX_LEN]

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO server_errors (route, error_type, message, traceback, request_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (route, error_type, message, tb_truncated, request_id),
            )
            conn.commit()
    except Exception as inner:
        logger.warning("log_server_error falló al persistir: %s", inner)
