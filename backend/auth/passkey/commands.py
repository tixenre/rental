"""Escrituras de credenciales passkey (tabla `passkey_credentials`) — única
puerta de mutación. Move-verbatim desde `auth/passkey/store.py` (reorg
CQRS-lite, espeja `contabilidad/`/`services/categorias/`): mismo SQL, mismo
comportamiento. Ver `auth/passkey/queries.py` para las lecturas.

`credential_id`/`public_key` se guardan en **base64url (TEXT)** — el browser
ya manda el `id` en base64url. Las escrituras de borrado/renombrado van
**scopeadas al dueño** (owner_type + cliente_id/owner_email) para que un
cliente no pueda tocar la credencial de otro (IDOR): el `WHERE` incluye el
dueño, no solo el `id`.
"""
from typing import Optional

from database import get_db, now_ar


def crear_cuenta_liviana_con_passkey(
    *,
    credential_id: str,
    public_key: str,
    sign_count: int,
    transports: Optional[str],
    aaguid: Optional[str],
    device_name: str,
    user_handle: str,
) -> int:
    """Alta passwordless (#1098 Fase 4): crea la cuenta-cliente **liviana** (sin
    nombre/mail/datos) y su passkey en UNA transacción atómica — si el insert de
    la credencial falla, no queda una cuenta huérfana. `owner_email=""` (la cuenta
    no tiene mail todavía; la columna es NOT NULL). Devuelve el `cliente_id`
    recién creado. Deja propagar `psycopg.errors.UniqueViolation` (credential_id
    ya registrado) — el caller (route) la traduce al 409 con su propio mensaje."""
    with get_db() as conn:
        with conn.transaction():
            cliente_id = conn.insert_returning(
                "INSERT INTO clientes (cuenta_estado) VALUES (%s)", ("liviana",)
            )
            conn.execute(
                """INSERT INTO passkey_credentials
                       (owner_type, owner_email, cliente_id, credential_id, public_key,
                        sign_count, transports, aaguid, device_name, user_handle)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                ("cliente", "", cliente_id, credential_id, public_key,
                 sign_count, transports, aaguid, device_name, user_handle),
            )
    return cliente_id


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
