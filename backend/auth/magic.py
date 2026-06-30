"""auth/magic.py — magic-link de UN SOLO USO (sobre `auth_challenges`).

Un token opaco que viaja por fuera (mail, o el link que el admin copia y manda) y que,
al consumirse, prueba control de ese canal. **Single-use:** el hash del nonce vive en
`auth_challenges`; consumirlo marca `used_at` de forma atómica → un link filtrado y ya
usado no sirve dos veces. El **contexto** (propósito + `cliente_id` + email) viaja en el
token FIRMADO (`auth.session.signer`), así no hace falta sumarle columnas a la tabla.

Lo usan: la **invitación de cuenta** (Fase 4 — el admin invita a reclamar una cuenta) y,
opcional, el **atajo de recuperación por mail** (Fase 3 — cuando ya hay mail; el camino
fuerte de recuperación es Didit/CUIL). Espeja el patrón del `reg_token` de Google
(`auth/google.py`) pero con single-use real.
"""
import hashlib
import secrets
from datetime import timedelta

from itsdangerous import BadSignature, SignatureExpired

from auth.session import signer
from database import get_db, now_ar

# TTL de una invitación: holgado (la persona puede no clickear al instante), pero acotado.
TTL = timedelta(days=7)


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def crear(*, email: str, purpose: str, cliente_id: int | None = None, conn=None) -> str:
    """Crea un magic-link single-use y devuelve el token OPACO (va por fuera). Guarda el
    hash de su nonce + expiración en `auth_challenges`. `purpose` ∈ {'invitacion',
    'recuperacion'} viaja firmado junto al `cliente_id` y el email."""
    raw = secrets.token_urlsafe(32)
    token = signer.dumps({"p": purpose, "cid": cliente_id, "email": (email or "").lower(), "k": raw})
    own = conn is None
    conn = conn or get_db()
    try:
        conn.execute(
            "INSERT INTO auth_challenges (kind, email, token_hash, expires_at) "
            "VALUES ('magic_link', %s, %s, %s)",
            ((email or "").lower(), _hash(raw), now_ar() + TTL),
        )
        conn.commit()
    finally:
        if own:
            conn.close()
    return token


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


def consumir(token: str, *, purpose: str, conn=None) -> dict | None:
    """Valida Y CONSUME (single-use) un magic-link. Devuelve `{cliente_id, email}` o `None`.
    `None` si: firma inválida/vencida, `purpose` distinto, o el nonce ya fue usado /
    no existe / venció en la tabla. El marcado de usado es ATÓMICO (UPDATE … WHERE
    used_at IS NULL … RETURNING) → dos requests en carrera no lo consumen dos veces."""
    try:
        data = signer.loads(token, max_age=int(TTL.total_seconds()))
    except (BadSignature, SignatureExpired):
        return None
    if data.get("p") != purpose:
        return None
    own = conn is None
    conn = conn or get_db()
    try:
        ahora = now_ar()
        row = conn.execute(
            "UPDATE auth_challenges SET used_at = %s, attempts = attempts + 1 "
            "WHERE token_hash = %s AND used_at IS NULL AND expires_at > %s "
            "RETURNING id",
            (ahora, _hash(data.get("k", "")), ahora),
        ).fetchone()
        conn.commit()
        if row is None:
            return None  # ya usado / inexistente / vencido
        return {"cliente_id": data.get("cid"), "email": data.get("email")}
    finally:
        if own:
            conn.close()
