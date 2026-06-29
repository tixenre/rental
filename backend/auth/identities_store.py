"""Persistencia de identidades de login del cliente (tabla `login_identities`).

Las N llaves —Google (`sub` estable) y mail— que apuntan a UNA cuenta (`clientes.id`).
Helpers finos sobre el DAL único, espejo de `passkey/store.py`. `UNIQUE(method,
identifier)` garantiza que una llave (un `sub`, un mail) apunte a una sola cuenta
(anti-duplicado de persona). Passkey NO vive acá (tiene su propia tabla con columnas
WebAuthn); "mis llaves" une las dos en lectura. Las escrituras de borrado van
scopeadas al dueño (`cliente_id` en el WHERE) — anti-IDOR, igual que passkey/store.
"""
from typing import Optional

from database import get_db, now_ar


def _row(r) -> dict:
    return {k: r[k] for k in r.keys()}


def find_cliente_by_identity(method: str, identifier: str) -> Optional[int]:
    """cliente_id dueño de la llave (method, identifier), o None. El caller normaliza
    `identifier` (mail en minúscula; `sub` tal cual de Google)."""
    with get_db() as conn:
        r = conn.execute(
            "SELECT cliente_id FROM login_identities WHERE method = %s AND identifier = %s",
            (method, identifier),
        ).fetchone()
    return r["cliente_id"] if r else None


def link_identity(*, cliente_id: int, method: str, identifier: str, verified: bool = True) -> str:
    """Vincula una llave a la cuenta. Devuelve:
      · 'linked'         — se creó la llave.
      · 'already_yours'  — ya era de esta cuenta (idempotente).
      · 'taken_by_other' — la llave es de OTRA cuenta (el caller responde 409).
    SELECT + INSERT en una transacción; el UNIQUE(method, identifier) es la red final."""
    with get_db() as conn:
        with conn.transaction():
            existing = conn.execute(
                "SELECT cliente_id FROM login_identities WHERE method = %s AND identifier = %s",
                (method, identifier),
            ).fetchone()
            if existing:
                return "already_yours" if existing["cliente_id"] == cliente_id else "taken_by_other"
            conn.execute(
                """INSERT INTO login_identities (cliente_id, method, identifier, verified_at)
                   VALUES (%s, %s, %s, %s)""",
                (cliente_id, method, identifier, now_ar() if verified else None),
            )
    return "linked"


def find_or_backfill_google(sub: Optional[str], email: str) -> Optional[int]:
    """Resuelve la cuenta para un login de Google: (1) por `sub` (ancla estable);
    (2) fallback por mail (cuentas previas a `login_identities`) → backfillea el `sub`
    para que la próxima sea por `sub`. None si no existe la cuenta (→ flujo de registro).
    El backfill migra a las cuentas viejas sin romperlas el día uno; y como matchea por
    `sub`, un cliente que cambió su mail en Google sigue entrando a la misma cuenta."""
    if sub:
        cid = find_cliente_by_identity("google", sub)
        if cid is not None:
            return cid
    with get_db() as conn:
        r = conn.execute(
            "SELECT id FROM clientes WHERE LOWER(email) = LOWER(%s)", (email,)
        ).fetchone()
    if r is None:
        return None
    cid = r["id"]
    if sub:
        link_identity(cliente_id=cid, method="google", identifier=sub, verified=True)
    return cid


def list_for_cliente(cliente_id: int) -> list[dict]:
    """Identidades (google/email) de la cuenta — para "métodos de acceso". El route
    une esto con las passkeys (otra tabla)."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, method, identifier, verified_at, created_at
               FROM login_identities WHERE cliente_id = %s
               ORDER BY created_at DESC""",
            (cliente_id,),
        ).fetchall()
    return [_row(r) for r in rows]


def count_for_cliente(cliente_id: int) -> int:
    """Cuántas identidades login_identities tiene la cuenta. El guard "no borres tu
    última llave" suma esto + las passkeys (las cuenta el route)."""
    with get_db() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS c FROM login_identities WHERE cliente_id = %s",
            (cliente_id,),
        ).fetchone()
    return r["c"]


def unlink_for_cliente(identity_pk: int, cliente_id: int) -> bool:
    """Borra SCOPEADO al dueño (anti-IDOR): el WHERE incluye `cliente_id`, no solo el
    `id`. Devuelve True si borró (False si no era suya). El guard de "última llave"
    vive en el route (cuenta también las passkeys)."""
    with get_db() as conn:
        with conn.transaction():
            r = conn.execute(
                "DELETE FROM login_identities WHERE id = %s AND cliente_id = %s RETURNING id",
                (identity_pk, cliente_id),
            ).fetchone()
    return r is not None
