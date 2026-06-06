"""
routes/auth.py — Google OAuth 2.0 + cookie de sesión firmada.
"""

import logging
import os
import time
from collections import defaultdict

from authlib.integrations.httpx_client import OAuth2Client
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from net_utils import get_client_ip
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Config ──────────────────────────────────────────────────────────────────

SECRET_KEY = settings.SECRET_KEY
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY no configurada — generá una con: "
        "python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# Base URL del backend. En Railway viene del entorno; en dev local usamos
# localhost:8000 (que el proxy de Vite reescribe). Las env vars REDIRECT_URI
# / CLIENTE_REDIRECT_URI tienen prioridad — si están seteadas se respetan
# tal cual (útil para staging u otros entornos custom).
def _default_oauth_base() -> str:
    # SITE_URL seteado explícitamente via env var → es el dominio canónico
    # (prod: www.ramblarental.com.ar, staging: rambla-rental-dev.up.railway.app).
    site_url = os.getenv("SITE_URL", "").strip()
    if site_url:
        return site_url
    if settings.is_railway:
        return "https://ramblarental.up.railway.app"
    return "http://localhost:8000"

_OAUTH_BASE          = _default_oauth_base()
REDIRECT_URI         = os.getenv("REDIRECT_URI")         or f"{_OAUTH_BASE}/auth/callback"
CLIENTE_REDIRECT_URI = os.getenv("CLIENTE_REDIRECT_URI") or f"{_OAUTH_BASE}/cliente/auth/callback"
POST_LOGIN_URL       = os.getenv("POST_LOGIN_URL", "/admin")
FRONTEND_BASE        = os.getenv("FRONTEND_BASE_URL", "")   # e.g. http://localhost:3000 en dev
MAPS_API_KEY         = os.getenv("GOOGLE_MAPS_API_KEY", "")

ALLOWED_EMAILS: set[str] = {
    e.strip().lower()
    for e in os.getenv("ALLOWED_EMAILS", "").split(",")
    if e.strip()
}

COOKIE_SECURE = settings.cookie_secure
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 días


def dev_bypass_enabled() -> bool:
    """¿Está activo el bypass de auth de dev (ADMIN_BYPASS_AUTH)?

    Seguridad (#503): NUNCA en producción. Aunque `ADMIN_BYPASS_AUTH` quede
    seteada por error en Railway, en un entorno Railway se ignora — el bypass
    es imposible de cara al público (no depende de verificar la config a mano).
    Fuente única usada por `require_admin`, `/auth/dev-login` y `/auth/config`.
    """
    if os.getenv("RAILWAY_ENVIRONMENT"):
        return False
    return os.getenv("ADMIN_BYPASS_AUTH", "").strip().lower() in ("1", "true", "yes")


GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO  = "https://www.googleapis.com/oauth2/v3/userinfo"

signer = URLSafeTimedSerializer(SECRET_KEY)

# ── Rate limiting (para /auth/callback) ─────────────────────────────────────

_failures: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 600
_RATE_MAX = 10


def _check_rate(ip: str) -> None:
    now = time.time()
    recent = [t for t in _failures[ip] if now - t < _RATE_WINDOW]
    _failures[ip] = recent
    if len(recent) >= _RATE_MAX:
        raise HTTPException(429, "Demasiados intentos. Intentá en 10 minutos.")


def _record_fail(ip: str) -> None:
    _failures[ip].append(time.time())


# ── Sesión ──────────────────────────────────────────────────────────────────

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


def _make_session_response(email: str, name: str, redirect: str | None = None):
    token = signer.dumps({"email": email, "name": name})
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
        res = JSONResponse({"ok": True, "email": email, "name": name})
    res.set_cookie(
        "session", token,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        max_age=SESSION_MAX_AGE,
    )
    return res


# ── Helpers OAuth ────────────────────────────────────────────────────────────

def _oauth_client() -> OAuth2Client:
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "Google OAuth no configurado en el servidor.")
    return OAuth2Client(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope="openid email profile",
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/auth/me")
def auth_me(request: Request):
    """Devuelve info de la sesión actual + flag `is_admin`.

    El flag es necesario para que el front sepa si renderizar el
    backoffice o redirect a una pantalla "sin acceso". `require_session`
    solo verifica que haya sesión válida (cualquier Google login), pero
    es admin solo si el email está en ADMIN_EMAILS.
    """
    # Import inline para evitar ciclo (admin_guard importa de routes.auth).
    from admin_guard import is_admin_email

    session = require_session(request)
    email = (session.get("email") or "").strip().lower()
    return {**session, "is_admin": is_admin_email(email)}


@router.get("/auth/logout")
def auth_logout():
    res = RedirectResponse(f"{FRONTEND_BASE}/admin/login", status_code=303)
    res.delete_cookie("session")
    return res


@router.post("/auth/logout")
def auth_logout_post():
    res = JSONResponse({"ok": True})
    res.delete_cookie("session")
    return res


@router.get("/auth/google")
def auth_google(request: Request):
    """Redirige al usuario a la pantalla de selección de cuenta de Google."""
    client = _oauth_client()
    uri, state = client.create_authorization_url(
        GOOGLE_AUTH_URL,
        access_type="online",
        prompt="select_account",
    )
    res = RedirectResponse(uri, status_code=302)
    # Guardamos el state en cookie para verificarlo en el callback
    res.set_cookie("oauth_state", state, httponly=True, samesite="lax",
                   secure=COOKIE_SECURE, max_age=600)
    return res


@router.get("/auth/callback")
def auth_callback(request: Request):
    """Google redirige acá con el código de autorización."""
    ip = get_client_ip(request)
    _check_rate(ip)

    error = request.query_params.get("error")
    if error:
        return RedirectResponse(f"{FRONTEND_BASE}/admin/login?error={error}", status_code=303)

    code  = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        return RedirectResponse(f"{FRONTEND_BASE}/admin/login?error=no_code", status_code=303)

    # Verificar state anti-CSRF
    saved_state = request.cookies.get("oauth_state")
    if not saved_state or saved_state != state:
        _record_fail(ip)
        return RedirectResponse(f"{FRONTEND_BASE}/admin/login?error=state_mismatch", status_code=303)

    # Intercambiar código por token
    client = _oauth_client()
    try:
        client.fetch_token(GOOGLE_TOKEN_URL, code=code)
    except Exception as e:
        logger.warning("Admin OAuth token_error: %s", e, exc_info=True)
        _record_fail(ip)
        return RedirectResponse(f"{FRONTEND_BASE}/admin/login?error=token_error", status_code=303)

    # Obtener datos del usuario — authlib ya tiene el token guardado tras fetch_token()
    try:
        resp = client.get(GOOGLE_USERINFO)
        resp.raise_for_status()
        userinfo = resp.json()
    except Exception as e:
        logger.warning("Admin OAuth userinfo_error: %s", e, exc_info=True)
        _record_fail(ip)
        return RedirectResponse(f"{FRONTEND_BASE}/admin/login?error=userinfo_error", status_code=303)

    email = userinfo.get("email", "").lower()
    name  = userinfo.get("name", email)

    if not email:
        _record_fail(ip)
        return RedirectResponse(f"{FRONTEND_BASE}/admin/login?error=no_email", status_code=303)

    # Verificar email autorizado
    if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
        _record_fail(ip)
        return RedirectResponse(f"{FRONTEND_BASE}/admin/login?error=not_allowed", status_code=303)

    res = _make_session_response(email, name, redirect=POST_LOGIN_URL)
    # Limpiar cookie de state
    res.delete_cookie("oauth_state")
    return res


@router.get("/auth/config")
def auth_config():
    dev_mode = dev_bypass_enabled()
    return {
        "google_enabled": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "dev_mode": dev_mode,
    }


@router.get("/auth/dev-login")
def auth_dev_login():
    """Login directo sin OAuth — solo en dev (ADMIN_BYPASS_AUTH=1, nunca en prod)."""
    if not dev_bypass_enabled():
        raise HTTPException(404, "No encontrado.")
    return _make_session_response(
        email="dev@local",
        name="Dev Admin",
        redirect="/admin",
    )


@router.get("/api/public/maps-key")
def public_maps_key():
    return {"key": MAPS_API_KEY or None}


# ── OAuth para clientes ───────────────────────────────────────────────────────

def _safe_next_path(raw: str | None) -> str | None:
    """Valida que `next` sea una ruta interna segura (no open-redirect).

    Acepta solo paths que empiezan con un único `/` (no `//`, que sería
    protocol-relative y abriría a otro dominio). Rechaza esquemas explícitos.
    Devuelve la ruta validada o None.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s.startswith("/"):
        return None
    if s.startswith("//") or s.startswith("/\\"):  # protocol-relative → otro host
        return None
    if ":" in s.split("/", 2)[1] if "/" in s[1:] else False:  # noqa: E501
        # Defensivo: si algún componente trae ':' antes de un '/' adicional,
        # podría intentarse `/\\example.com:443/x` u otros tricks. Rechazamos.
        return None
    # Tope de longitud razonable (URL-encoded params se inflan).
    if len(s) > 2048:
        return None
    return s


@router.get("/cliente/auth/google")
def cliente_auth_google(request: Request):
    """Inicia el flujo OAuth de Google para clientes.

    Si llega `?next=<path>`, la guardamos en cookie para volver ahí después del
    login en vez de mandar siempre a /cliente/portal. Solo aceptamos paths
    internos (validación en `_safe_next_path` — no open-redirect).
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "Google OAuth no configurado en el servidor.")
    client = OAuth2Client(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        redirect_uri=CLIENTE_REDIRECT_URI,
        scope="openid email profile",
    )
    uri, state = client.create_authorization_url(
        GOOGLE_AUTH_URL,
        access_type="online",
        prompt="select_account",
    )
    res = RedirectResponse(uri, status_code=302)
    res.set_cookie("oauth_state_cliente", state, httponly=True, samesite="lax",
                   secure=COOKIE_SECURE, max_age=600)
    next_path = _safe_next_path(request.query_params.get("next"))
    if next_path:
        res.set_cookie(
            "oauth_next_cliente", next_path, httponly=True, samesite="lax",
            secure=COOKIE_SECURE, max_age=600,
        )
    return res


@router.get("/cliente/auth/callback")
def cliente_auth_callback(request: Request):
    """Google redirige acá. Si el cliente existe → sesión. Si no → registro."""
    from database import get_db

    ip = get_client_ip(request)
    _check_rate(ip)

    error = request.query_params.get("error")
    if error:
        return RedirectResponse(f"{FRONTEND_BASE}/cliente/login?error={error}", status_code=303)

    code  = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        return RedirectResponse(f"{FRONTEND_BASE}/cliente/login?error=no_code", status_code=303)

    saved_state = request.cookies.get("oauth_state_cliente")
    if not saved_state or saved_state != state:
        _record_fail(ip)
        return RedirectResponse(f"{FRONTEND_BASE}/cliente/login?error=state_mismatch", status_code=303)

    client = OAuth2Client(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        redirect_uri=CLIENTE_REDIRECT_URI,
        scope="openid email profile",
    )
    try:
        client.fetch_token(GOOGLE_TOKEN_URL, code=code)
    except Exception as e:
        logger.warning("Cliente OAuth token_error: %s", e, exc_info=True)
        _record_fail(ip)
        return RedirectResponse(f"{FRONTEND_BASE}/cliente/login?error=token_error", status_code=303)

    try:
        resp = client.get(GOOGLE_USERINFO)
        resp.raise_for_status()
        userinfo = resp.json()
    except Exception as e:
        logger.warning("Cliente OAuth userinfo_error: %s", e, exc_info=True)
        _record_fail(ip)
        return RedirectResponse(f"{FRONTEND_BASE}/cliente/login?error=userinfo_error", status_code=303)

    email = userinfo.get("email", "").lower()
    name  = userinfo.get("name", email)

    if not email:
        _record_fail(ip)
        return RedirectResponse(f"{FRONTEND_BASE}/cliente/login?error=no_email", status_code=303)

    # ¿El cliente ya existe en la BD?
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM clientes WHERE LOWER(email) = LOWER(?)", (email,)
        ).fetchone()
    finally:
        conn.close()

    if row:
        # Cliente conocido → crear sesión directamente. Si llegó `next` válido
        # (cookie seteada por /cliente/auth/google), volvemos ahí en vez de al
        # portal — habilita el flujo de "iniciar sesión y volver a /estudio".
        session_data = {"email": email, "name": name, "role": "cliente", "cliente_id": row["id"]}
        token = signer.dumps(session_data)
        next_path = _safe_next_path(request.cookies.get("oauth_next_cliente"))
        target = f"{FRONTEND_BASE}{next_path}" if next_path else f"{FRONTEND_BASE}/cliente/portal"
        safe_url = target.replace('"', "%22")
        res = HTMLResponse(
            f'<!DOCTYPE html><html><head>'
            f'<script>window.location.replace("{safe_url}")</script>'
            f'</head><body>Redirigiendo...</body></html>'
        )
        res.set_cookie("session", token, httponly=True, samesite="lax",
                       secure=COOKIE_SECURE, max_age=SESSION_MAX_AGE)
        res.delete_cookie("oauth_state_cliente")
        res.delete_cookie("oauth_next_cliente")
        return res
    else:
        # Cliente nuevo → token de registro (válido 30 min). El `next` lo
        # descartamos: el flujo de registro lleva su propio camino y el cliente
        # podrá navegar al destino después de completar el alta.
        reg_token = signer.dumps({"tipo": "registro", "email": email, "name": name})
        redirect_url = f"{FRONTEND_BASE}/cliente/registro?t={reg_token}"
        res = RedirectResponse(redirect_url, status_code=303)
        res.delete_cookie("oauth_state_cliente")
        res.delete_cookie("oauth_next_cliente")
        return res
