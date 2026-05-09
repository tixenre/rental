"""
supabase_auth.py — Verificación de JWT emitidos por Supabase Auth.

Permite que el frontend Lovable (que usa Supabase Auth) llame a este backend
adjuntando `Authorization: Bearer <jwt>`. El JWT se valida contra el JWKS
público del proyecto Supabase y se hace upsert del cliente en la tabla
`clientes` por `supabase_uid`.

Uso típico:
    from supabase_auth import get_supabase_cliente

    @router.get("/api/cliente/me")
    def me(request: Request):
        cliente = get_supabase_cliente(request)  # raises 401 if no/bad token
        return cliente

Variables de entorno:
    SUPABASE_PROJECT_URL   ej: https://ytujjqoffcdsdowfqaex.supabase.co
"""

from __future__ import annotations

import os
import time
from typing import Optional

import httpx
import jwt
from fastapi import HTTPException, Request

from database import get_db, row_to_dict

SUPABASE_PROJECT_URL = os.getenv(
    "SUPABASE_PROJECT_URL",
    "https://ytujjqoffcdsdowfqaex.supabase.co",
).rstrip("/")

JWKS_URL = f"{SUPABASE_PROJECT_URL}/auth/v1/.well-known/jwks.json"

# Cache JWKS en memoria. Supabase rota llaves rara vez; refrescamos cada 1h.
_jwks_cache: dict = {}
_jwks_fetched_at: float = 0.0
_JWKS_TTL_SECONDS = 3600


def _get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    now = time.time()
    if _jwks_cache and (now - _jwks_fetched_at) < _JWKS_TTL_SECONDS:
        return _jwks_cache
    try:
        resp = httpx.get(JWKS_URL, timeout=5.0)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = now
    except Exception as e:
        # Si no podemos refrescar pero tenemos cache vieja, la usamos.
        if not _jwks_cache:
            raise HTTPException(503, f"No se pudo obtener JWKS de Supabase: {e}")
    return _jwks_cache


def _key_for_token(token: str):
    """Resuelve la JWK que firmó este JWT a partir del header `kid`."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"JWT inválido: {e}")

    kid = header.get("kid")
    alg = header.get("alg", "RS256")
    jwks = _get_jwks()

    for jwk in jwks.get("keys", []):
        if jwk.get("kid") == kid:
            return jwt.algorithms.get_default_algorithms()[alg].from_jwk(jwk), alg

    # Fallback: si no hay match, intentar refrescar JWKS una vez
    global _jwks_fetched_at
    _jwks_fetched_at = 0.0
    jwks = _get_jwks()
    for jwk in jwks.get("keys", []):
        if jwk.get("kid") == kid:
            return jwt.algorithms.get_default_algorithms()[alg].from_jwk(jwk), alg

    raise HTTPException(401, "JWT firmado por una llave desconocida")


def verify_supabase_jwt(token: str) -> dict:
    """Valida el JWT y devuelve el payload (claims). Raises HTTPException(401) si falla."""
    key, alg = _key_for_token(token)
    try:
        payload = jwt.decode(
            token,
            key=key,
            algorithms=[alg],
            audience="authenticated",
            options={"require": ["sub", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"Token inválido: {e}")

    if not payload.get("sub"):
        raise HTTPException(401, "Token sin subject")
    return payload


def _extract_bearer(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth:
        return None
    parts = auth.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def get_supabase_claims(request: Request) -> Optional[dict]:
    """Devuelve los claims del JWT si el header Bearer está presente y es válido.
    Si no hay header, devuelve None (no eleva). Si el header existe pero es inválido,
    eleva 401."""
    token = _extract_bearer(request)
    if not token:
        return None
    return verify_supabase_jwt(token)


def upsert_cliente_from_claims(claims: dict) -> dict:
    """Asegura que exista un cliente vinculado al supabase_uid del JWT.
    Devuelve el row completo del cliente (dict)."""
    supabase_uid = claims["sub"]
    email = (claims.get("email") or "").strip().lower()
    full_name = (
        claims.get("user_metadata", {}).get("full_name")
        or claims.get("user_metadata", {}).get("name")
        or ""
    ).strip()
    nombre, _, apellido = full_name.partition(" ")
    nombre = nombre or (email.split("@")[0] if email else "Cliente")
    apellido = apellido or "-"

    conn = get_db()
    try:
        # 1) Match por supabase_uid
        row = conn.execute(
            "SELECT * FROM clientes WHERE supabase_uid = ?", (supabase_uid,)
        ).fetchone()
        if row:
            return row_to_dict(row)

        # 2) Match por email (cliente preexistente del back-office) → linkear
        if email:
            row = conn.execute(
                "SELECT * FROM clientes WHERE LOWER(email) = LOWER(?)", (email,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE clientes SET supabase_uid = ? WHERE id = ?",
                    (supabase_uid, row["id"]),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT * FROM clientes WHERE id = ?", (row["id"],)
                ).fetchone()
                return row_to_dict(row)

        # 3) Crear cliente nuevo (mínimo viable; perfil se completa después)
        conn.execute(
            """
            INSERT INTO clientes
                (nombre, apellido, telefono, email, direccion, cuit,
                 perfil_impuestos, supabase_uid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nombre,
                apellido,
                "-",
                email or f"{supabase_uid}@no-email.local",
                "-",
                "-",
                "consumidor_final",
                supabase_uid,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM clientes WHERE supabase_uid = ?", (supabase_uid,)
        ).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def get_supabase_cliente(request: Request) -> dict:
    """Dependency: exige Bearer JWT válido y devuelve el cliente asociado.
    Eleva HTTPException(401) si no hay token o es inválido."""
    claims = get_supabase_claims(request)
    if not claims:
        raise HTTPException(401, "Authorization Bearer requerido")
    return upsert_cliente_from_claims(claims)


# ─── Admin guard ────────────────────────────────────────────────────────
#
# Lista de emails con acceso admin. Se configura por env var ADMIN_EMAILS
# (CSV) y/o se mantiene un fallback hardcodeado para desarrollo.
_ADMIN_EMAILS_ENV = os.getenv("ADMIN_EMAILS", "tinchosantini@gmail.com")
ADMIN_EMAILS: set[str] = {
    e.strip().lower() for e in _ADMIN_EMAILS_ENV.split(",") if e.strip()
}


def is_admin_email(email: Optional[str]) -> bool:
    if not email:
        return False
    return email.strip().lower() in ADMIN_EMAILS


def require_admin(request: Request) -> dict:
    """Dependency para endpoints del back-office.

    Acepta dos formas de auth (en este orden):
      1. Bearer JWT de Supabase + email en ADMIN_EMAILS  → frontend Lovable.
      2. Cookie de sesión clásica del FastAPI            → back-office HTML viejo.

    Si la env var ADMIN_BYPASS_AUTH=1 está seteada, deja pasar a cualquiera
    (modo desarrollo / web aún no funcional). NUNCA dejar esto en prod abierto.
    """
    if os.getenv("ADMIN_BYPASS_AUTH", "").strip() in ("1", "true", "yes"):
        return {"kind": "bypass", "email": "bypass@local"}

    # 1) Bearer JWT
    try:
        claims = get_supabase_claims(request)
    except HTTPException:
        claims = None
    if claims:
        email = (claims.get("email") or "").strip().lower()
        if is_admin_email(email):
            return {"kind": "supabase", "email": email, "claims": claims}
        raise HTTPException(403, "Tu cuenta no tiene permisos de administración")

    # 2) Cookie de sesión clásica
    try:
        from routes.auth import get_session  # import local para evitar ciclos
        session = get_session(request)
    except Exception:
        session = None
    if session:
        email = (session.get("email") or session.get("usuario") or "").strip().lower()
        return {"kind": "session", "email": email, "session": session}

    raise HTTPException(401, "Autenticación requerida (admin)")
