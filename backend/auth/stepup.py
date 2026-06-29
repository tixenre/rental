"""auth/stepup.py — step-up con passkey ("confirmá que sos vos") para acciones sensibles.

Primitivo **reusable** (#1098): probar identidad con una passkey **fresca** antes de una
operación sensible (quitar una llave de acceso; en el futuro, confirmar un pedido). No es
un login (ya hay sesión): la ceremonia de passkey verifica que sos vos AHORA y deja una
marca de corta vida (cookie firmada `stepup`, ~5 min) que el guard `require_recent_auth`
exige. Reusa la misma assertion WebAuthn que el login (`auth/passkey/ceremonies`).

La marca es **owner-scoped** (lleva el `cliente_id`): una marca de otra cuenta no sirve.
"""
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import HTTPException, Request

from config import settings
from auth.guards import require_cliente
from auth.session import COOKIE_SECURE

STEPUP_COOKIE = "stepup"
STEPUP_MAX_AGE = 300  # 5 min: ventana para completar la acción tras confirmar con la passkey

_signer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="passkey-stepup")


def mark_stepup(res, cliente_id: int) -> None:
    """Deja la marca de step-up reciente (cookie firmada de corta vida) tras una
    confirmación con passkey exitosa."""
    res.set_cookie(
        STEPUP_COOKIE, _signer.dumps({"cid": cliente_id}),
        max_age=STEPUP_MAX_AGE, httponly=True, samesite="lax", secure=COOKIE_SECURE,
    )


def has_recent_stepup(request: Request, cliente_id: int) -> bool:
    """True si hay una marca de step-up válida (firmada, fresca) para esta cuenta."""
    tok = request.cookies.get(STEPUP_COOKIE)
    if not tok:
        return False
    try:
        data = _signer.loads(tok, max_age=STEPUP_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return isinstance(data, dict) and data.get("cid") == cliente_id


def require_recent_auth(request: Request) -> dict:
    """Como `require_cliente` pero además exige un step-up con passkey **reciente**
    (cookie `stepup` fresca + de esta cuenta). 401 si falta → el front dispara el step-up
    y reintenta. Gate de operaciones sensibles del cliente (quitar llave; futuro: pedidos)."""
    sess = require_cliente(request)
    if not has_recent_stepup(request, sess["cliente_id"]):
        raise HTTPException(401, "Confirmá tu identidad con tu passkey para esta acción.")
    return sess
