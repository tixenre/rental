"""
routes/auth.py — Google OAuth 2.0 + cookie de sesión firmada.
"""

import os
import time
from collections import defaultdict

from authlib.integrations.httpx_client import OAuth2Client
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

router = APIRouter()

# ── Config ──────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY no configurada — generá una con: "
        "python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI         = os.getenv("REDIRECT_URI", "https://ramblarental.up.railway.app/auth/callback")
MAPS_API_KEY         = os.getenv("GOOGLE_MAPS_API_KEY", "")

ALLOWED_EMAILS: set[str] = {
    e.strip().lower()
    for e in os.getenv("ALLOWED_EMAILS", "").split(",")
    if e.strip()
}

COOKIE_SECURE = (
    os.getenv("RAILWAY_ENVIRONMENT") is not None
    or os.getenv("COOKIE_SECURE", "").lower() == "true"
)
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 días

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
        res = RedirectResponse(redirect, status_code=303)
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
    return require_session(request)


@router.get("/auth/logout")
def auth_logout():
    res = RedirectResponse("/admin/login", status_code=303)
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
    ip = request.client.host if request.client else "unknown"
    _check_rate(ip)

    error = request.query_params.get("error")
    if error:
        return RedirectResponse(f"/admin/login?error={error}", status_code=303)

    code  = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        return RedirectResponse("/admin/login?error=no_code", status_code=303)

    # Verificar state anti-CSRF
    saved_state = request.cookies.get("oauth_state")
    if not saved_state or saved_state != state:
        _record_fail(ip)
        return RedirectResponse("/admin/login?error=state_mismatch", status_code=303)

    # Intercambiar código por token
    client = _oauth_client()
    try:
        token = client.fetch_token(GOOGLE_TOKEN_URL, code=code)
    except Exception:
        _record_fail(ip)
        return RedirectResponse("/admin/login?error=token_error", status_code=303)

    # Obtener datos del usuario
    try:
        resp = client.get(GOOGLE_USERINFO, token=token)
        resp.raise_for_status()
        userinfo = resp.json()
    except Exception:
        _record_fail(ip)
        return RedirectResponse("/admin/login?error=userinfo_error", status_code=303)

    email = userinfo.get("email", "").lower()
    name  = userinfo.get("name", email)

    if not email:
        _record_fail(ip)
        return RedirectResponse("/admin/login?error=no_email", status_code=303)

    # Verificar email autorizado
    if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
        _record_fail(ip)
        return RedirectResponse("/admin/login?error=not_allowed", status_code=303)

    res = _make_session_response(email, name, redirect="/admin")
    # Limpiar cookie de state
    res.delete_cookie("oauth_state")
    return res


@router.get("/auth/config")
def auth_config():
    dev_mode = os.getenv("ADMIN_BYPASS_AUTH", "").strip() in ("1", "true", "yes")
    return {
        "google_enabled": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "dev_mode": dev_mode,
    }


@router.get("/auth/dev-login")
def auth_dev_login():
    """Login directo sin OAuth — solo funciona con ADMIN_BYPASS_AUTH=1."""
    if os.getenv("ADMIN_BYPASS_AUTH", "").strip() not in ("1", "true", "yes"):
        raise HTTPException(403, "Solo disponible en modo desarrollo.")
    return _make_session_response(
        email="dev@local",
        name="Dev Admin",
        redirect="/admin",
    )


@router.get("/api/public/maps-key")
def public_maps_key():
    return {"key": MAPS_API_KEY or None}
