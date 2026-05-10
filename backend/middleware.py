"""
middleware.py — Protección de rutas con cookie de sesión.
"""

from fastapi import Request
from fastapi.responses import RedirectResponse, JSONResponse
from routes.auth import get_session

PUBLIC_EXACT = {"/", "/login", "/admin/login", "/cliente", "/health"}

PUBLIC_PREFIXES = (
    "/auth/google",
    "/auth/callback",
    "/auth/logout",
    "/auth/me",
    "/auth/config",
    "/auth/dev-login",
    "/static/",
    "/assets/",
    "/equipo/",
    "/cliente/",
)

PUBLIC_API = (
    "/api/equipos",
    "/api/categorias",
    "/api/etiquetas",
    "/api/disponibilidad",
    "/api/public/",
)


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if path in PUBLIC_EXACT:
        return await call_next(request)
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)
    if any(path.startswith(p) for p in PUBLIC_API):
        return await call_next(request)

    session = get_session(request)
    if not session:
        if path.startswith("/api/"):
            return JSONResponse({"detail": "No autenticado"}, status_code=401)
        return RedirectResponse("/login")

    return await call_next(request)
