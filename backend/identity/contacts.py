"""identity/contacts.py — contactos verificados (mail/teléfono).

`verified_contacts` son los factores de **comunicación + recuperación** de una
cuenta: mail (verificado por Google OAuth o por código de Didit) y teléfono
(verificado por OTP/WhatsApp de Didit, en E.164). Acá se guardan (upsert) y se
deriva el contacto de comunicación.

Regla de comunicación (decisión del dueño): **el mail de Google es el preferido**
(verificado por OAuth y disponible desde el alta) → fallback al de Didit (para
cuentas passkey-only, que no tienen Google). El teléfono NO es llave de login.
"""

from database import get_db, now_ar, row_to_dict
from services.didit.decision import ContactoVerificado, ContactosVerificados


def upsert_contacto(
    conn,
    *,
    cliente_id: int,
    kind: str,
    value: str,
    source: str,
    verified_at=None,
    is_disposable: bool | None = None,
    is_virtual: bool | None = None,
    is_breached: bool | None = None,
) -> None:
    """Inserta o actualiza un contacto verificado (owner-scoped). UNIQUE
    (cliente_id, kind, value): re-verificar el mismo contacto refresca metadata."""
    conn.execute(
        """INSERT INTO verified_contacts
               (cliente_id, kind, value, source, verified_at,
                is_disposable, is_virtual, is_breached)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (cliente_id, kind, value) DO UPDATE
             SET source=EXCLUDED.source,
                 verified_at=COALESCE(EXCLUDED.verified_at, verified_contacts.verified_at),
                 is_disposable=COALESCE(EXCLUDED.is_disposable, verified_contacts.is_disposable),
                 is_virtual=COALESCE(EXCLUDED.is_virtual, verified_contacts.is_virtual),
                 is_breached=COALESCE(EXCLUDED.is_breached, verified_contacts.is_breached)""",
        (cliente_id, kind, value, source, verified_at or now_ar(),
         is_disposable, is_virtual, is_breached),
    )


def _guardar_uno(conn, cliente_id: int, c: ContactoVerificado | None) -> None:
    if c is None or not c.value:
        return
    upsert_contacto(
        conn,
        cliente_id=cliente_id,
        kind=c.kind,
        value=c.value,
        source="didit",
        verified_at=c.verified_at,
        is_disposable=c.is_disposable,
        is_virtual=c.is_virtual,
        is_breached=c.is_breached,
    )


def guardar_contactos_didit(conn, cliente_id: int, contactos: ContactosVerificados) -> None:
    """Persiste los contactos verificados que devolvió Didit (mail + teléfono)."""
    _guardar_uno(conn, cliente_id, contactos.email)
    _guardar_uno(conn, cliente_id, contactos.phone)


def email_comunicacion(conn, cliente_id: int) -> str | None:
    """Mail de comunicación: Google (base `clientes.email`, desde el alta) preferido
    → fallback al verificado por Didit (passkey-only). None si no hay ninguno."""
    row = conn.execute("SELECT email FROM clientes WHERE id=%s", (cliente_id,)).fetchone()
    base = row_to_dict(row).get("email") if row else None
    if base:
        return base  # el de Google: verificado por OAuth y disponible desde el alta
    r = conn.execute(
        "SELECT value FROM verified_contacts WHERE cliente_id=%s AND kind='email' "
        "ORDER BY verified_at DESC NULLS LAST LIMIT 1",
        (cliente_id,),
    ).fetchone()
    return row_to_dict(r).get("value") if r else None


def telefono_contacto(conn, cliente_id: int) -> str | None:
    """Teléfono de contacto: el verificado (E.164, de Didit) preferido → fallback al
    base `clientes.telefono`. None si no hay ninguno."""
    r = conn.execute(
        "SELECT value FROM verified_contacts WHERE cliente_id=%s AND kind='phone' "
        "ORDER BY verified_at DESC NULLS LAST LIMIT 1",
        (cliente_id,),
    ).fetchone()
    if r:
        return row_to_dict(r).get("value")
    row = conn.execute("SELECT telefono FROM clientes WHERE id=%s", (cliente_id,)).fetchone()
    return row_to_dict(row).get("telefono") if row else None
