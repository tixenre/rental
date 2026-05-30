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
    "/api/cotizar",  # cotización del carrito: pública (catálogo anónimo cotiza
    # como consumidor_final). No escribe; los descuentos/IVA de cliente requieren
    # sesión adentro del handler (get_session), así que abrirla es seguro.
    "/api/public/",
    "/api/cliente/registro",  # registro-info y registro (sin sesión)
    # /api/estudio expone la config del espacio (incluyendo pack curado) y la
    # disponibilidad por franja — son lecturas públicas. La creación de reservas
    # vive bajo /api/estudio/reservas y tiene su propio `_require_cliente` en el
    # handler, así que el guard de cliente se sigue aplicando ahí.
    "/api/estudio",
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
