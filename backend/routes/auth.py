"""
routes/auth.py — Google OAuth 2.0 + cookie de sesión firmada.
"""

import logging
import os
import secrets
import time
from collections import defaultdict

from authlib.integrations.httpx_client import OAuth2Client
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import BaseModel

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
MAPS_API_KEY         = settings.GOOGLE_MAPS_API_KEY

ALLOWED_EMAILS: set[str] = {
    e.strip().lower()
    for e in os.getenv("ALLOWED_EMAILS", "").split(",")
    if e.strip()
}

COOKIE_SECURE = settings.cookie_secure
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 días


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


# Cuenta de servicio para login programático en STAGING (no en prod). Email
# dedicado y auditable: para que sea admin debe estar en `ADMIN_EMAILS` del
# entorno dev (la admin-ness la sigue resolviendo `is_admin_email`, fuente
# única; este login no la saltea). Override por env si hace falta otro.
STAGING_LOGIN_EMAIL = os.getenv("STAGING_LOGIN_EMAIL", "staging-bot@rambla.local").strip().lower()

# Cliente de servicio para impersonar el PORTAL DEL CLIENTE en staging (target
# "cliente" de `/auth/staging-login`). Se busca por este email salvo que el body
# pase un `cliente_id` puntual. Como staging es copia de prod, también sirve
# impersonar cualquier cliente real existente por id.
STAGING_CLIENTE_EMAIL = os.getenv("STAGING_CLIENTE_EMAIL", "staging-cliente@rambla.local").strip().lower()


def _staging_login_secret() -> str:
    """Secreto compartido para `/auth/staging-login` (env var, solo dev)."""
    return os.getenv("STAGING_LOGIN_SECRET", "").strip()


def staging_login_enabled() -> bool:
    """¿Está disponible el login programático de staging?

    Doble llave, ambas necesarias (defensa en profundidad):
      1. NO es producción — usa `settings.is_production`, que falla hacia "sí es
         prod" ante un nombre de entorno desconocido, así que un ambiente nuevo
         mal nombrado queda con el login APAGADO, no abierto.
      2. Hay un secreto configurado — sin `STAGING_LOGIN_SECRET` el endpoint no
         existe ni siquiera en dev.

    Por qué el secreto es obligatorio: la BD de staging es copia de prod (ver
    MEMORIA / `Settings.is_production`), o sea tiene PII real de clientes. Un
    login abierto en una URL pública de dev sería una fuga. El secreto vive solo
    en el entorno dev de Railway, nunca en el repo, y es rotable.
    """
    if settings.is_production:
        return False
    return bool(_staging_login_secret())


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

    if dev_bypass_enabled():
        return {"email": "bypass@local", "name": "Dev Admin", "is_admin": True}

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
    # State firmado: verificable por firma en el callback, sin depender de cookie.
    # Resuelve state_mismatch en browsers con ITP/strict mode/ad-blockers.
    state = signer.dumps({"nonce": secrets.token_urlsafe(16)})
    client = _oauth_client()
    uri, _ = client.create_authorization_url(
        GOOGLE_AUTH_URL,
        state=state,
        access_type="online",
        prompt="select_account",
    )
    res = RedirectResponse(uri, status_code=302)
    # Cookie como capa extra (browsers sin bloqueo la usan; los que bloquean
    # pasan igual porque la firma del state es suficiente).
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

    # Verificar state anti-CSRF: cookie match (ideal) o firma válida (fallback
    # para browsers con ITP/strict mode/ad-blockers que bloquean la cookie).
    saved_state = request.cookies.get("oauth_state")
    state_ok = bool(saved_state and saved_state == state)
    if not state_ok and state:
        try:
            signer.loads(state, max_age=600)
            state_ok = True
            if not saved_state:
                logger.info("admin OAuth: state por firma (sin cookie) ip=%s", ip)
        except (BadSignature, SignatureExpired):
            pass
    if not state_ok:
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


def _resolve_staging_cliente(cliente_id: int | None) -> dict | None:
    """Resuelve el cliente a impersonar en staging (target="cliente"). READ-ONLY:
    solo lee `clientes`, nunca muta staging. Por `cliente_id` si se pasa; si no,
    por `STAGING_CLIENTE_EMAIL`. Devuelve `{id, email, name}` o None si no existe."""
    from database import get_db

    with get_db() as conn:
        if cliente_id is not None:
            row = conn.execute(
                "SELECT id, nombre, apellido, email FROM clientes WHERE id = ?",
                (cliente_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, nombre, apellido, email FROM clientes WHERE LOWER(email) = LOWER(?)",
                (STAGING_CLIENTE_EMAIL,),
            ).fetchone()
    if not row:
        return None
    nombre = f"{row['nombre'] or ''} {row['apellido'] or ''}".strip()
    return {"id": row["id"], "email": row["email"], "name": nombre or row["email"]}


class StagingLoginInput(BaseModel):
    secret: str
    # "admin" (default, sesión de back-office) o "cliente" (sesión del portal del
    # cliente). Backward-compatible: sin `target` se comporta como antes.
    target: str = "admin"
    # Solo para target="cliente": impersonar un cliente puntual por id. Si se
    # omite, se usa el cliente de servicio `STAGING_CLIENTE_EMAIL`.
    cliente_id: int | None = None


@router.post("/auth/staging-login")
def auth_staging_login(body: StagingLoginInput, request: Request):
    """Login programático para STAGING (dev de Railway), sin el flujo OAuth de Google.

    A diferencia de `/auth/dev-login` (que se apaga en CUALQUIER entorno Railway),
    este SÍ corre en el `dev` de Railway — pero solo si `staging_login_enabled()`
    (no-prod + secreto configurado). Mintea la misma cookie de sesión firmada que
    el OAuth real. Devuelve JSON + `Set-Cookie` (sin redirect HTML), para que un
    cliente automatizado capture la cookie y pruebe flujos autenticados en staging.

    Dos targets (la admin-ness y la cliente-ness las siguen resolviendo
    `is_admin_email` / `require_cliente`, fuentes únicas — este login no las saltea):
      - "admin" (default): sesión de back-office para `STAGING_LOGIN_EMAIL`.
      - "cliente": sesión del PORTAL para un cliente real existente (`role` +
        `cliente_id`), resuelto por `_resolve_staging_cliente`. No crea clientes.

    Seguridad: 404 si no está habilitado (que parezca inexistente en prod);
    secreto en body comparado en tiempo constante; rate-limit por IP compartido
    con OAuth; cada intento queda logueado.
    """
    if not staging_login_enabled():
        raise HTTPException(404, "No encontrado.")
    ip = get_client_ip(request)
    _check_rate(ip)
    expected = _staging_login_secret()
    if not (body.secret and secrets.compare_digest(body.secret, expected)):
        _record_fail(ip)
        logger.warning("staging-login: secreto inválido ip=%s", ip)
        raise HTTPException(401, "Secreto inválido.")

    target = (body.target or "admin").strip().lower()
    if target == "cliente":
        cli = _resolve_staging_cliente(body.cliente_id)
        if not cli:
            raise HTTPException(
                404,
                "Cliente de staging no encontrado. Pasá un `cliente_id` existente "
                f"o creá el cliente `{STAGING_CLIENTE_EMAIL}` en staging.",
            )
        logger.info("staging-login OK (cliente) ip=%s cliente_id=%s", ip, cli["id"])
        return _make_session_response(
            email=cli["email"], name=cli["name"],
            extra={"role": "cliente", "cliente_id": cli["id"]},
        )
    if target != "admin":
        raise HTTPException(400, "target inválido (usá 'admin' o 'cliente').")

    logger.info("staging-login OK (admin) ip=%s email=%s", ip, STAGING_LOGIN_EMAIL)
    return _make_session_response(email=STAGING_LOGIN_EMAIL, name="Staging Bot")


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
    # XSS hardening: el valor se embebe en el HTML+JS del callback
    # (<script>…replace("{next}")…</script>). Rechazar caracteres que permitan
    # romper ese contexto (`<`/`>` → `</script>`, comillas, backtick, backslash)
    # o whitespace/control — un path interno legítimo no los necesita.
    if any(c in s for c in "<>\"'`\\") or any(c.isspace() or ord(c) < 0x20 for c in s):
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
    state = signer.dumps({"nonce": secrets.token_urlsafe(16)})
    uri, _ = client.create_authorization_url(
        GOOGLE_AUTH_URL,
        state=state,
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
    state_ok = bool(saved_state and saved_state == state)
    if not state_ok and state:
        try:
            signer.loads(state, max_age=600)
            state_ok = True
            if not saved_state:
                logger.info("cliente OAuth: state por firma (sin cookie) ip=%s", ip)
        except (BadSignature, SignatureExpired):
            pass
    if not state_ok:
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
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM clientes WHERE LOWER(email) = LOWER(?)", (email,)
        ).fetchone()

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
