"""Persistencia de credenciales passkey (tabla `passkey_credentials`).

Helpers finos sobre el DAL único (`PGConnection`). `credential_id` / `public_key`
se guardan en **base64url (TEXT)** — el browser ya manda el `id` en base64url, así
el lookup de login es comparación de texto directa, sin bytea/memoryview.

Las escrituras de borrado/renombrado van **scopeadas al dueño** (owner_type +
cliente_id/owner_email) para que un cliente no pueda tocar la credencial de otro
(IDOR): el `WHERE` incluye el dueño, no solo el `id`.
"""
from typing import Optional

from database import get_db, now_ar


def _row(r) -> dict:
    return {k: r[k] for k in r.keys()}


def insert_credential(
    *,
    owner_type: str,
    owner_email: str,
    cliente_id: Optional[int],
    credential_id: str,
    public_key: str,
    sign_count: int,
    transports: Optional[str],
    aaguid: Optional[str],
    device_name: str,
    user_handle: str,
) -> int:
    with get_db() as conn:
        with conn.transaction():
            return conn.insert_returning(
                """INSERT INTO passkey_credentials
                       (owner_type, owner_email, cliente_id, credential_id, public_key,
                        sign_count, transports, aaguid, device_name, user_handle)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (owner_type, owner_email, cliente_id, credential_id, public_key,
                 sign_count, transports, aaguid, device_name, user_handle),
            )


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


def update_sign_count(cred_pk: int, new_count: int) -> None:
    with get_db() as conn:
        with conn.transaction():
            conn.execute(
                "UPDATE passkey_credentials SET sign_count = %s, last_used_at = %s WHERE id = %s",
                (new_count, now_ar(), cred_pk),
            )


def delete_for_owner(
    cred_pk: int, owner_type: str, *, owner_email: Optional[str] = None, cliente_id: Optional[int] = None
) -> bool:
    """Borra SCOPEADO al dueño. Devuelve True si borró (False si no era suya)."""
    with get_db() as conn:
        with conn.transaction():
            if owner_type == "cliente":
                r = conn.execute(
                    "DELETE FROM passkey_credentials "
                    "WHERE id = %s AND owner_type = 'cliente' AND cliente_id = %s RETURNING id",
                    (cred_pk, cliente_id),
                ).fetchone()
            else:
                r = conn.execute(
                    "DELETE FROM passkey_credentials "
                    "WHERE id = %s AND owner_type = 'admin' AND LOWER(owner_email) = LOWER(%s) RETURNING id",
                    (cred_pk, owner_email),
                ).fetchone()
    return r is not None


def rename_for_owner(
    cred_pk: int, device_name: str, owner_type: str, *, owner_email: Optional[str] = None,
    cliente_id: Optional[int] = None,
) -> bool:
    """Renombra SCOPEADO al dueño. Devuelve True si renombró."""
    with get_db() as conn:
        with conn.transaction():
            if owner_type == "cliente":
                r = conn.execute(
                    "UPDATE passkey_credentials SET device_name = %s "
                    "WHERE id = %s AND owner_type = 'cliente' AND cliente_id = %s RETURNING id",
                    (device_name, cred_pk, cliente_id),
                ).fetchone()
            else:
                r = conn.execute(
                    "UPDATE passkey_credentials SET device_name = %s "
                    "WHERE id = %s AND owner_type = 'admin' AND LOWER(owner_email) = LOWER(%s) RETURNING id",
                    (device_name, cred_pk, owner_email),
                ).fetchone()
    return r is not None
