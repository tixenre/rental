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

# Centinela para distinguir "sesión aún no resuelta" de "resuelta = None" en el
# cache por-request (None es un valor válido: no hay sesión).
_UNSET = object()


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
    """Resuelve la sesión del request: valida la firma Y que la sesión siga viva en
    la allowlist server-side (revocación). Toda sesión válida lleva `jti` y está en
    la tabla; una cookie sin jti se rechaza. Memoiza el resultado en `request.state`
    para que los 2-3 llamados de un mismo request (middleware + guard + handler)
    hagan un solo lookup a la DB."""
    state = getattr(request, "state", None)
    if state is not None:
        cached = getattr(state, "_auth_session", _UNSET)
        if cached is not _UNSET:
            return cached
    resolved = _resolve_session(request)
    if state is not None:
        try:
            state._auth_session = resolved
        except Exception:  # noqa: BLE001 — sin request.state utilizable seguimos sin cache (correcto, solo menos óptimo)
            pass
    return resolved


def _resolve_session(request: Request) -> dict | None:
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        data = signer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    # Revocación server-side: TODA sesión válida tiene que estar viva en la allowlist.
    # Una cookie sin `jti` (las viejas pre-deploy, las hand-minted) se rechaza → el
    # usuario re-loguea y obtiene una sesión revocable. Así no queda NINGUNA sesión
    # fuera de la tabla (invariante fuerte: todo es revocable desde el minuto uno).
    jti = data.get("jti") if isinstance(data, dict) else None
    if not jti:
        return None
    from auth import sessions_store  # perezoso: rompe el ciclo con auth/__init__
    if sessions_store.is_active(jti) is None:
        return None
    return data


def require_session(request: Request) -> dict:
    session = get_session(request)
    if not session:
        raise HTTPException(401, "No autenticado")
    return session


def _make_session_response(
    email: str, name: str, redirect: str | None = None,
    extra: dict | None = None, request: Request | None = None,
):
    """Mintea la cookie de sesión firmada. `extra` agrega campos a la sesión
    (ej. `role`/`cliente_id` para una sesión de cliente); sin él, sesión de admin
    como siempre.

    Registra además la sesión server-side (allowlist `auth_sessions`) con un `jti`
    opaco que viaja firmado en la cookie → habilita la revocación (logout real +
    "cerrar mis otras sesiones"). Es el **punto único de minteo** (Google admin/
    cliente, passkey y staging pasan por acá), así el `jti` se crea en un solo lugar.
    `request` (si se pasa) aporta el user_agent para mostrar el dispositivo."""
    payload = {"email": email, "name": name}
    if extra:
        payload.update(extra)

    from auth import sessions_store  # perezoso: rompe el ciclo con auth/__init__
    owner_type = "cliente" if (extra or {}).get("role") == "cliente" else "admin"
    user_agent = request.headers.get("user-agent") if request is not None else None
    jti = sessions_store.create_session(
        owner_type=owner_type,
        owner_email=email,
        cliente_id=(extra or {}).get("cliente_id"),
        ttl_segundos=SESSION_MAX_AGE,
        user_agent=user_agent,
    )

    # El `jti` viaja SOLO dentro de la cookie firmada (lo lee get_session para
    # revocar); NO se expone en el body JSON de respuesta — no hace falta y reduce
    # superficie. El body se arma de `payload` (sin jti).
    token = signer.dumps({**payload, "jti": jti})
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
