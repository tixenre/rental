"""Escrituras de identidades de login del cliente (tabla `login_identities`) —
única puerta de mutación. Move-verbatim desde `auth/identities_store.py` (reorg
CQRS-lite, espeja `contabilidad/`/`passkey/`): mismo SQL, mismo comportamiento.
Ver `auth/queries/identities.py` para las lecturas.
"""
from typing import Optional

from database import get_db, now_ar
from auth.queries.identities import find_cliente_by_identity


def link_identity(
    *, cliente_id: int, method: str, identifier: str, email: Optional[str] = None,
    verified: bool = True,
) -> str:
    """Vincula una llave a la cuenta. Devuelve:
      · 'linked'         — se creó la llave.
      · 'already_yours'  — ya era de esta cuenta (idempotente; refresca el `email`).
      · 'taken_by_other' — la llave es de OTRA cuenta (el caller responde 409).
    SELECT + INSERT en una transacción; el UNIQUE(method, identifier) es la red final.
    `email` es solo display (el mail del Google linkeado); el ancla es `identifier`."""
    with get_db() as conn:
        with conn.transaction():
            existing = conn.execute(
                "SELECT cliente_id FROM login_identities WHERE method = %s AND identifier = %s",
                (method, identifier),
            ).fetchone()
            if existing:
                if existing["cliente_id"] != cliente_id:
                    return "taken_by_other"
                if email:  # refresca el mail de display si cambió
                    conn.execute(
                        "UPDATE login_identities SET email = %s "
                        "WHERE method = %s AND identifier = %s",
                        (email, method, identifier),
                    )
                return "already_yours"
            conn.execute(
                """INSERT INTO login_identities (cliente_id, method, identifier, email, verified_at)
                   VALUES (%s, %s, %s, %s, %s)""",
                (cliente_id, method, identifier, email, now_ar() if verified else None),
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
        link_identity(cliente_id=cid, method="google", identifier=sub, email=email, verified=True)
    return cid


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
