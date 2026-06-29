"""auth/session.py — núcleo de la sesión (fuente única).

La cookie firmada `session` es el punto donde convergen TODOS los métodos de login
(Google OAuth y passkey): la mintea `_make_session_response` y la leen los guards.
`signer` es una instancia ÚNICA — todo el resto la importa de acá.

Movido verbatim de `routes/auth.py` (consolidación de auth).
"""
import os

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import settings

SECRET_KEY = settings.SECRET_KEY
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY no configurada — generá una con: "
        "python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

COOKIE_SECURE = settings.cookie_secure
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 días

signer = URLSafeTimedSerializer(SECRET_KEY)


def dev_bypass_enabled() -> bool:
    """¿Está activo el bypass de auth de dev (ADMIN_BYPASS_AUTH)?

    Seguridad (#503): NUNCA en producción. Bloquea cuando RAILWAY_ENVIRONMENT
    es explícitamente 'production'; en Railway dev/staging y en local se
    permite si ADMIN_BYPASS_AUTH=1. Falla-cerrada: si alguien pone la var en
    prod, RAILWAY_ENVIRONMENT=production la anula.
    Fuente única usada por `require_admin`, `/auth/dev-login`, `/auth/me`
    y `/auth/config`.
    """
    if os.getenv("RAILWAY_ENVIRONMENT", "").strip().lower() == "production":
        return False
    return os.getenv("ADMIN_BYPASS_AUTH", "").strip().lower() in ("1", "true", "yes")


def get_session(request: Request) -> dict | None:
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        return signer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def require_session(request: Request) -> dict:
    session = get_session(request)
    if not session:
        raise HTTPException(401, "No autenticado")
    return session


def _make_session_response(
    email: str, name: str, redirect: str | None = None, extra: dict | None = None
):
    """Mintea la cookie de sesión firmada. `extra` agrega campos a la sesión
    (ej. `role`/`cliente_id` para una sesión de cliente); sin él, sesión de admin
    como siempre."""
    payload = {"email": email, "name": name}
    if extra:
        payload.update(extra)
    token = signer.dumps(payload)
    if redirect:
        # Use 200 + JS redirect so the browser processes Set-Cookie before navigating.
        # A 303 redirect through the Vite proxy drops Set-Cookie headers.
        safe_url = redirect.replace('"', "%22")
        res = HTMLResponse(
            f'<!DOCTYPE html><html><head>'
            f'<script>window.location.replace("{safe_url}")</script>'
            f'</head><body>Redirigiendo...</body></html>'
        )
    else:
        res = JSONResponse({"ok": True, **payload})
    res.set_cookie(
        "session", token,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        max_age=SESSION_MAX_AGE,
    )
    return res
