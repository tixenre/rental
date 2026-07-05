"""Lectura del magic-link single-use (sobre `auth_challenges`) — nunca muta.

Move-verbatim desde `auth/magic.py` (reorg CQRS-lite, espeja `contabilidad/`/
`identities/`): mismo SQL, mismo comportamiento. `TTL`/`_hash` viven acá (no en
`commands/`, que las importa) porque `peek` los necesita y `queries/` nunca
importa de `commands/`. Ver `auth/commands/magic.py` para `crear`/`consumir`.
"""
import hashlib
from datetime import timedelta

from itsdangerous import BadSignature, SignatureExpired

from auth.session import signer
from database import get_db, now_ar

# TTL de una invitación: holgado (la persona puede no clickear al instante), pero acotado.
TTL = timedelta(days=7)


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def peek(token: str, *, purpose: str, conn=None) -> dict | None:
    """Valida SIN consumir (para previsualizar la invitación en el landing). Devuelve
    `{cliente_id, email}` o `None` (firma inválida/vencida, purpose distinto, o ya
    usado/vencido en la tabla). El single-use real lo hace `consumir` al reclamar."""
    try:
        data = signer.loads(token, max_age=int(TTL.total_seconds()))
    except (BadSignature, SignatureExpired):
        return None
    if data.get("p") != purpose:
        return None
    own = conn is None
    conn = conn or get_db()
    try:
        row = conn.execute(
            "SELECT 1 FROM auth_challenges "
            "WHERE token_hash = %s AND used_at IS NULL AND expires_at > %s",
            (_hash(data.get("k", "")), now_ar()),
        ).fetchone()
        return {"cliente_id": data.get("cid"), "email": data.get("email")} if row else None
    finally:
        if own:
            conn.close()
