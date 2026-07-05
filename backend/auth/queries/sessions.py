"""Lecturas de sesiones server-side (tabla `auth_sessions`) — nunca mutan.

Move-verbatim desde `auth/sessions_store.py` (reorg CQRS-lite, espeja
`contabilidad/`/`services/categorias/`): mismo SQL, mismo comportamiento.
Ver `auth/commands/sessions.py` para las escrituras (create/revoke/purge).
"""
from typing import Optional

from database import get_db, now_ar


def _row(r) -> dict:
    return {k: r[k] for k in r.keys()}


def is_active(jti: str) -> Optional[dict]:
    """La sesión del `jti` si está VIVA (no revocada y no vencida); None si no.
    Es el chequeo del hot-path (lo llama `get_session` en cada request autenticado)."""
    with get_db() as conn:
        r = conn.execute(
            """SELECT jti, owner_type, owner_email, cliente_id
               FROM auth_sessions
               WHERE jti = %s AND revoked_at IS NULL AND expires_at > %s""",
            (jti, now_ar()),
        ).fetchone()
    return _row(r) if r else None


def list_for_owner(
    owner_type: str, *, owner_email: Optional[str] = None, cliente_id: Optional[int] = None
) -> list[dict]:
    """Lista las sesiones VIVAS del dueño (para la pantalla de gestión), recientes
    primero. Trae lo justo para mostrar: dispositivo (user_agent) + fechas + jti
    (para marcar 'este dispositivo' y permitir revocar una)."""
    with get_db() as conn:
        if owner_type == "cliente":
            rows = conn.execute(
                """SELECT jti, user_agent, created_at, expires_at
                   FROM auth_sessions
                   WHERE owner_type = 'cliente' AND cliente_id = %s
                     AND revoked_at IS NULL AND expires_at > %s
                   ORDER BY created_at DESC""",
                (cliente_id, now_ar()),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT jti, user_agent, created_at, expires_at
                   FROM auth_sessions
                   WHERE owner_type = 'admin' AND LOWER(owner_email) = LOWER(%s)
                     AND revoked_at IS NULL AND expires_at > %s
                   ORDER BY created_at DESC""",
                (owner_email, now_ar()),
            ).fetchall()
    return [_row(r) for r in rows]
