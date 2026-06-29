"""Persistencia de sesiones server-side (tabla `auth_sessions`).

Allowlist para revocación: la cookie firmada lleva un `jti` opaco y esta tabla
decide si la sesión sigue viva (`revoked_at IS NULL AND expires_at > now`). Helpers
finos sobre el DAL único (`PGConnection`), espejando `auth/passkey/store.py`.

Las escrituras de revocación van **scopeadas al dueño** (owner_type + cliente_id /
owner_email) para que un cliente no pueda matar la sesión de otro (IDOR): el `WHERE`
incluye el dueño, no solo el `jti`. Tiempos en wall-clock de AR vía `now_ar()`
(misma convención que el resto del backend: `expires_at` y la comparación usan la
misma zona, independiente de la TZ del server).
"""
from datetime import timedelta
from typing import Optional

import secrets

from database import get_db, now_ar


def _row(r) -> dict:
    return {k: r[k] for k in r.keys()}


def create_session(
    *,
    owner_type: str,
    owner_email: str,
    cliente_id: Optional[int],
    ttl_segundos: int,
    user_agent: Optional[str] = None,
) -> str:
    """Crea la fila de sesión y devuelve el `jti` opaco (el id de la sesión que va
    firmado en la cookie). El `jti` es secreto-aleatorio: nadie lo adivina."""
    jti = secrets.token_urlsafe(32)
    ahora = now_ar()
    expires_at = ahora + timedelta(seconds=ttl_segundos)
    with get_db() as conn:
        with conn.transaction():
            conn.execute(
                """INSERT INTO auth_sessions
                       (jti, owner_type, owner_email, cliente_id, user_agent,
                        created_at, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (jti, owner_type, owner_email, cliente_id, user_agent, ahora, expires_at),
            )
    return jti


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


def revoke(jti: str) -> None:
    """Revoca una sesión por `jti` (logout del propio dueño). Idempotente."""
    with get_db() as conn:
        with conn.transaction():
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = %s "
                "WHERE jti = %s AND revoked_at IS NULL",
                (now_ar(), jti),
            )


def revoke_all_for_owner(
    owner_type: str,
    *,
    owner_email: Optional[str] = None,
    cliente_id: Optional[int] = None,
    except_jti: Optional[str] = None,
) -> int:
    """Revoca TODAS las sesiones vivas del dueño, opcionalmente salvo `except_jti`
    (el dispositivo que pide la acción, para no auto-desloguearse). Devuelve cuántas
    revocó. Scopeada al dueño (owner_type + cliente_id/owner_email)."""
    ahora = now_ar()
    with get_db() as conn:
        with conn.transaction():
            if owner_type == "cliente":
                rows = conn.execute(
                    "UPDATE auth_sessions SET revoked_at = %s "
                    "WHERE owner_type = 'cliente' AND cliente_id = %s "
                    "AND revoked_at IS NULL AND (%s IS NULL OR jti <> %s) "
                    "RETURNING jti",
                    (ahora, cliente_id, except_jti, except_jti),
                ).fetchall()
            else:
                rows = conn.execute(
                    "UPDATE auth_sessions SET revoked_at = %s "
                    "WHERE owner_type = 'admin' AND LOWER(owner_email) = LOWER(%s) "
                    "AND revoked_at IS NULL AND (%s IS NULL OR jti <> %s) "
                    "RETURNING jti",
                    (ahora, owner_email, except_jti, except_jti),
                ).fetchall()
    return len(rows)


def revoke_one_for_owner(
    jti: str,
    owner_type: str,
    *,
    owner_email: Optional[str] = None,
    cliente_id: Optional[int] = None,
) -> bool:
    """Revoca UNA sesión SCOPEADA al dueño (anti-IDOR: el `WHERE` incluye al dueño,
    no solo el `jti`). True si revocó (False si no era suya o ya estaba revocada)."""
    with get_db() as conn:
        with conn.transaction():
            if owner_type == "cliente":
                r = conn.execute(
                    "UPDATE auth_sessions SET revoked_at = %s "
                    "WHERE jti = %s AND owner_type = 'cliente' AND cliente_id = %s "
                    "AND revoked_at IS NULL RETURNING jti",
                    (now_ar(), jti, cliente_id),
                ).fetchone()
            else:
                r = conn.execute(
                    "UPDATE auth_sessions SET revoked_at = %s "
                    "WHERE jti = %s AND owner_type = 'admin' AND LOWER(owner_email) = LOWER(%s) "
                    "AND revoked_at IS NULL RETURNING jti",
                    (now_ar(), jti, owner_email),
                ).fetchone()
    return r is not None


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


def purge_expired() -> int:
    """Borra filas vencidas (housekeeping). NO agendado en v1 — las filas muertas
    son inertes (is_active/list ya filtran por expires_at/revoked_at). Queda lista
    para un job futuro si la tabla crece. Devuelve cuántas borró."""
    with get_db() as conn:
        with conn.transaction():
            rows = conn.execute(
                "DELETE FROM auth_sessions WHERE expires_at <= %s RETURNING jti",
                (now_ar(),),
            ).fetchall()
    return len(rows)
