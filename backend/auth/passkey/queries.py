"""Lecturas de credenciales passkey (tabla `passkey_credentials`) — nunca mutan.

Move-verbatim desde `auth/passkey/store.py` (reorg CQRS-lite, espeja
`contabilidad/`/`services/categorias/`): mismo SQL, mismo comportamiento.
Ver `auth/passkey/commands.py` para las escrituras.
"""
from typing import Optional

from database import get_db


def _row(r) -> dict:
    return {k: r[k] for k in r.keys()}


def get_by_credential_id(credential_id: str) -> Optional[dict]:
    """Lookup por credential_id (login discoverable). Trae lo necesario para
    verificar la assertion y mintear la sesión del dueño."""
    with get_db() as conn:
        r = conn.execute(
            """SELECT id, owner_type, owner_email, cliente_id, public_key, sign_count
               FROM passkey_credentials WHERE credential_id = %s""",
            (credential_id,),
        ).fetchone()
    return _row(r) if r else None


def list_for_owner(
    owner_type: str, *, owner_email: Optional[str] = None, cliente_id: Optional[int] = None
) -> list[dict]:
    """Lista (para la pantalla de gestión) las passkeys del dueño."""
    with get_db() as conn:
        if owner_type == "cliente":
            rows = conn.execute(
                """SELECT id, device_name, transports, created_at, last_used_at
                   FROM passkey_credentials
                   WHERE owner_type = 'cliente' AND cliente_id = %s
                   ORDER BY created_at DESC""",
                (cliente_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, device_name, transports, created_at, last_used_at
                   FROM passkey_credentials
                   WHERE owner_type = 'admin' AND LOWER(owner_email) = LOWER(%s)
                   ORDER BY created_at DESC""",
                (owner_email,),
            ).fetchall()
    return [_row(r) for r in rows]


def credential_ids_for_owner(
    owner_type: str, *, owner_email: Optional[str] = None, cliente_id: Optional[int] = None
) -> list[str]:
    """credential_ids del dueño — para `excludeCredentials` (no re-registrar el
    mismo autenticador)."""
    with get_db() as conn:
        if owner_type == "cliente":
            rows = conn.execute(
                "SELECT credential_id FROM passkey_credentials "
                "WHERE owner_type = 'cliente' AND cliente_id = %s",
                (cliente_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT credential_id FROM passkey_credentials "
                "WHERE owner_type = 'admin' AND LOWER(owner_email) = LOWER(%s)",
                (owner_email,),
            ).fetchall()
    return [r["credential_id"] for r in rows]
