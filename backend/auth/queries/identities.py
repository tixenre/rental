"""Lecturas de identidades de login del cliente (tabla `login_identities`) —
nunca mutan.

Move-verbatim desde `auth/identities_store.py` (reorg CQRS-lite, espeja
`contabilidad/`/`passkey/`): mismo SQL, mismo comportamiento. Ver
`auth/commands/identities.py` para las escrituras.
"""
from typing import Optional

from database import get_db


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


def google_identity_for_cliente(cliente_id: int) -> Optional[dict]:
    """La identidad Google de la cuenta (sub + email), o None. Para el guardrail
    "una cuenta = un Google" (rechazar vincular un segundo Google distinto)."""
    with get_db() as conn:
        r = conn.execute(
            "SELECT id, identifier, email FROM login_identities "
            "WHERE cliente_id = %s AND method = 'google' LIMIT 1",
            (cliente_id,),
        ).fetchone()
    return _row(r) if r else None


def list_for_cliente(cliente_id: int) -> list[dict]:
    """Identidades (google/email) de la cuenta — para "métodos de acceso". El route
    une esto con las passkeys (otra tabla)."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, method, identifier, email, verified_at, created_at
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
