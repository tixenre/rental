"""
routes/auth.py — Login local (email+contraseña) y Google OAuth 2.0 (opcional)
"""

import os
import time
import httpx
import hashlib
import secrets
from collections import defaultdict
from urllib.parse import quote

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from database import get_db

router = APIRouter()

# ── Config desde variables de entorno ────────────────────────────────────────

CLIENT_ID      = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET  = os.getenv("GOOGLE_CLIENT_SECRET", "")
MAPS_API_KEY   = os.getenv("GOOGLE_MAPS_API_KEY", "")
SECRET_KEY     = os.getenv("SECRET_KEY", "dev-secret-cambiame-en-produccion")
if not SECRET_KEY or SECRET_KEY == "dev-secret-cambiame-en-produccion":
    raise RuntimeError("SECRET_KEY no configurada — generá una con: python3 -c \"import secrets; print(secrets.token_hex(32))\"")

REDIRECT_URI   = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")
# Emails autorizados separados por coma, ej: "juan@gmail.com,maria@gmail.com"
ALLOWED_EMAILS = set(
    e.strip() for e in os.getenv("ALLOWED_EMAILS", "").split(",") if e.strip()
)
# Cookie segura solo en producción (HTTPS). En desarrollo local se permite HTTP.
COOKIE_SECURE = os.getenv("RAILWAY_ENVIRONMENT") is not None or os.getenv("COOKIE_SECURE", "").lower() == "true"

SESSION_MAX_AGE = 60 * 60 * 24 * 30   # 30 días en segundos

signer = URLSafeTimedSerializer(SECRET_KEY)

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO  = "https://www.googleapis.com/oauth2/v3/userinfo"


# ── Password hashing (sin dependencias extra) ────────────────────────────────

def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"{salt}:{h.hex()}"

def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
        return secrets.compare_digest(candidate.hex(), h)
    except Exception:
        return False

def _needs_setup() -> bool:
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    conn.close()
    return count == 0


# ── Rate limiting para login local ───────────────────────────────────────────

_login_failures: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 600   # segundos (10 minutos)
_RATE_MAX    = 5     # intentos fallidos antes de bloquear


def _check_rate_limit(ip: str) -> None:
    now    = time.time()
    recent = [t for t in _login_failures[ip] if now - t < _RATE_WINDOW]
    _login_failures[ip] = recent
    if len(recent) >= _RATE_MAX:
        raise HTTPException(429, "Demasiados intentos fallidos. Intentá en 10 minutos.")


def _record_failed_login(ip: str) -> None:
    _login_failures[ip].append(time.time())


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_session(request: Request) -> dict | None:
    """Devuelve los datos de sesión o None si no hay sesión válida."""
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        return signer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def require_session(request: Request) -> dict:
    """Lanza 401 si no hay sesión válida."""
    session = get_session(request)
    if not session:
        raise HTTPException(401, "No autenticado")
    return session


# ── Rutas ────────────────────────────────────────────────────────────────────

@router.get("/auth/login")
def auth_login(request: Request, tipo: str = "admin"):
    """Redirige a Google para iniciar el flujo OAuth.
    tipo=admin → sesión de administrador (ALLOWED_EMAILS)
    tipo=cliente → sesión de cliente (tabla clientes)
    """
    if not CLIENT_ID:
        raise HTTPException(500, "GOOGLE_CLIENT_ID no configurado")
    nonce = secrets.token_urlsafe(16)
    # Codificar tipo en el state para recuperarlo en el callback
    state = f"{tipo}:{nonce}"
    params = "&".join([
        f"client_id={CLIENT_ID}",
        f"redirect_uri={REDIRECT_URI}",
        "response_type=code",
        "scope=openid%20email%20profile",
        "access_type=offline",
        "prompt=select_account",
        f"state={state}",
    ])
    response = RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}")
    response.set_cookie("oauth_state", state, httponly=True, samesite="lax",
                        secure=COOKIE_SECURE, max_age=300)
    return response


@router.get("/auth/callback")
async def auth_callback(request: Request, code: str = "", error: str = "", state: str = ""):
    """Google redirige aquí con el código de autorización."""
    if error:
        return RedirectResponse(f"/login?error={error}")
    if not code:
        return RedirectResponse("/login?error=sin_codigo")

    # Validar state para prevenir CSRF
    expected_state = request.cookies.get("oauth_state", "")
    if not expected_state or state != expected_state:
        return RedirectResponse("/login?error=estado_invalido")

    # Extraer tipo del state (formato: "tipo:nonce")
    tipo = "admin"
    if ":" in expected_state:
        tipo = expected_state.split(":", 1)[0]
    login_error_redirect = "/cliente?error=no_autorizado" if tipo == "cliente" else "/login?error=no_autorizado"

    # Intercambiar código por tokens
    async with httpx.AsyncClient() as client:
        token_res = await client.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri":  REDIRECT_URI,
            "grant_type":    "authorization_code",
        })

    tokens = token_res.json()
    access_token = tokens.get("access_token")
    if not access_token:
        return RedirectResponse("/login?error=token_fallido")

    # Obtener info del usuario
    async with httpx.AsyncClient() as client:
        info_res = await client.get(
            GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    info = info_res.json()
    email = info.get("email", "")
    name  = info.get("name", email)

    if tipo == "cliente":
        # Buscar el email en la tabla de clientes
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id, nombre, apellido FROM clientes WHERE LOWER(email) = LOWER(?)",
                (email,)
            ).fetchone()
        finally:
            conn.close()
        if not row:
            # Email no registrado → redirigir al formulario de alta
            reg_token = signer.dumps({"email": email, "name": name, "tipo": "registro"})
            return RedirectResponse(f"/cliente/registro?t={quote(reg_token)}")
        session_data = {
            "email":      email,
            "name":       name,
            "role":       "cliente",
            "cliente_id": row["id"],
        }
        redirect_to = "/cliente/portal"
    else:
        # Verificar email autorizado como admin
        if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
            return RedirectResponse(login_error_redirect)
        session_data = {"email": email, "name": name, "role": "admin"}
        redirect_to = "/admin"

    token = signer.dumps(session_data)
    response = RedirectResponse(redirect_to)
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        max_age=SESSION_MAX_AGE,
    )
    response.delete_cookie("oauth_state")
    return response


@router.get("/auth/logout")
def auth_logout():
    response = RedirectResponse("/login")
    response.delete_cookie("session")
    return response


@router.get("/auth/me")
def auth_me(request: Request):
    session = require_session(request)
    return session


# ── Config ────────────────────────────────────────────────────────────────────

@router.get("/api/public/maps-key")
def public_maps_key():
    """API key pública de Google Maps (Places Autocomplete). Ninguna auth requerida."""
    return {"key": MAPS_API_KEY or None}


@router.get("/auth/config")
def auth_config():
    """Informa al front qué métodos de login están disponibles."""
    return {
        "google":      bool(CLIENT_ID),
        "setup_needed": _needs_setup(),
    }


# ── Login local ───────────────────────────────────────────────────────────────

@router.post("/auth/login-local")
async def auth_login_local(request: Request):
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)

    body = await request.json()
    email    = body.get("email", "").strip().lower()
    password = body.get("password", "")
    if not email or not password:
        raise HTTPException(400, "Email y contraseña requeridos")

    conn = get_db()
    row = conn.execute(
        "SELECT nombre, password_hash FROM usuarios WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    if not row or not _verify_password(password, row["password_hash"]):
        _record_failed_login(ip)
        raise HTTPException(401, "Email o contraseña incorrectos")

    token = signer.dumps({"email": email, "name": row["nombre"]})
    res   = JSONResponse({"ok": True})
    res.set_cookie("session", token, httponly=True, samesite="lax", secure=COOKIE_SECURE, max_age=SESSION_MAX_AGE)
    return res


# ── Registro (solo disponible cuando no hay usuarios) ────────────────────────

@router.post("/auth/register")
async def auth_register(request: Request):
    if not _needs_setup():
        raise HTTPException(403, "El registro está cerrado")

    body     = await request.json()
    nombre   = body.get("nombre", "").strip()
    email    = body.get("email", "").strip().lower()
    password = body.get("password", "")

    if not nombre or not email or not password:
        raise HTTPException(400, "Completá todos los campos")
    if len(password) < 8:
        raise HTTPException(400, "La contraseña debe tener al menos 8 caracteres")

    pw_hash = _hash_password(password)

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO usuarios (email, nombre, password_hash) VALUES (?,?,?)",
            (email, nombre, pw_hash),
        )
        conn.commit()
    except Exception:
        conn.close()
        raise HTTPException(409, "Ese email ya está registrado")
    conn.close()

    token = signer.dumps({"email": email, "name": nombre})
    res   = JSONResponse({"ok": True})
    res.set_cookie("session", token, httponly=True, samesite="lax", secure=COOKIE_SECURE, max_age=SESSION_MAX_AGE)
    return res
