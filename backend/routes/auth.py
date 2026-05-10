"""
routes/auth.py — Login local (email + contraseña) con cookie de sesión.
Sin Google OAuth.
"""

import os
import time
import hashlib
import secrets
from collections import defaultdict

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from database import get_db

router = APIRouter()

# ── Config ──────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-cambiame-en-produccion")
if not SECRET_KEY or SECRET_KEY == "dev-secret-cambiame-en-produccion":
    raise RuntimeError(
        "SECRET_KEY no configurada — generá una con: "
        "python3 -c \"import secrets; print(secrets.token_hex(32))\""
    )

MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
COOKIE_SECURE = (
    os.getenv("RAILWAY_ENVIRONMENT") is not None
    or os.getenv("COOKIE_SECURE", "").lower() == "true"
)
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 días

signer = URLSafeTimedSerializer(SECRET_KEY)


# ── Password hashing ────────────────────────────────────────────────────────

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


# ── Rate limiting ───────────────────────────────────────────────────────────

_login_failures: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 600
_RATE_MAX = 5


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    recent = [t for t in _login_failures[ip] if now - t < _RATE_WINDOW]
    _login_failures[ip] = recent
    if len(recent) >= _RATE_MAX:
        raise HTTPException(429, "Demasiados intentos fallidos. Intentá en 10 minutos.")


def _record_failed_login(ip: str) -> None:
    _login_failures[ip].append(time.time())


# ── Sesión ──────────────────────────────────────────────────────────────────

def get_session(request: Request):
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


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/auth/me")
def auth_me(request: Request):
    return require_session(request)


@router.get("/auth/logout")
def auth_logout():
    res = RedirectResponse("/", status_code=303)
    res.delete_cookie("session")
    return res


@router.post("/auth/logout")
def auth_logout_post():
    res = JSONResponse({"ok": True})
    res.delete_cookie("session")
    return res


@router.get("/auth/config")
def auth_config():
    return {"setup_needed": _needs_setup()}


@router.get("/api/public/maps-key")
def public_maps_key():
    return {"key": MAPS_API_KEY or None}


@router.post("/auth/login-local")
async def auth_login_local(request: Request):
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)

    body = await request.json()
    email = body.get("email", "").strip().lower()
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
    res = JSONResponse({"ok": True, "email": email, "name": row["nombre"]})
    res.set_cookie(
        "session", token, httponly=True, samesite="lax",
        secure=COOKIE_SECURE, max_age=SESSION_MAX_AGE,
    )
    return res


@router.post("/auth/register")
async def auth_register(request: Request):
    if not _needs_setup():
        raise HTTPException(403, "El registro está cerrado")

    body = await request.json()
    nombre = body.get("nombre", "").strip()
    email = body.get("email", "").strip().lower()
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
    res = JSONResponse({"ok": True, "email": email, "name": nombre})
    res.set_cookie(
        "session", token, httponly=True, samesite="lax",
        secure=COOKIE_SECURE, max_age=SESSION_MAX_AGE,
    )
    return res
