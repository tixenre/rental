"""
middleware.py — Protección de rutas con sesión.

Acepta dos métodos de auth:
  1. Cookie de sesión firmada (cliente_portal y admin clásicos)
  2. Authorization: Bearer <jwt> emitido por Supabase Auth (frontend Lovable)
"""

from fastapi import Request
from fastapi.responses import RedirectResponse, JSONResponse
from routes.auth import get_session
from supabase_auth import get_supabase_claims

# Rutas exactas que NO requieren autenticación
PUBLIC_EXACT = {"/", "/login", "/cliente"}

# Prefijos que NO requieren autenticación
PUBLIC_PREFIXES = (
    "/auth/",
    "/static/",
    "/assets/",   # bundles JS/CSS del frontend Vite
    "/equipo/",    # fichas públicas
    "/cliente/",   # portal de clientes (autenticación propia)
)

# Rutas de API que son públicas (catálogo, disponibilidad, config)
PUBLIC_API = (
    "/api/equipos",
    "/api/categorias",
    "/api/etiquetas",
    "/api/disponibilidad",
    "/api/public/",
)


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # Permitir rutas exactas públicas
    if path in PUBLIC_EXACT:
        return await call_next(request)

    # Permitir rutas por prefijo
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)

    # APIs públicas del catálogo
    if any(path.startswith(p) for p in PUBLIC_API):
        return await call_next(request)

    # 1) Bearer JWT de Supabase (frontend Lovable)
    try:
        claims = get_supabase_claims(request)
    except Exception:
        # Si el header existe pero es inválido, dejamos que el endpoint
        # decida (algunos pueden requerir cliente, otros no).
        claims = None
    if claims:
        request.state.supabase_claims = claims
        return await call_next(request)

    # 2) Cookie de sesión clásica
    session = get_session(request)
    if not session:
        if path.startswith("/api/"):
            return JSONResponse({"detail": "No autenticado"}, status_code=401)
        return RedirectResponse("/login")

    return await call_next(request)
