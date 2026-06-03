"""
middleware.py — Protección de rutas con cookie de sesión.
"""

from fastapi import Request
from fastapi.responses import RedirectResponse, JSONResponse
from routes.auth import get_session

PUBLIC_EXACT = {"/", "/login", "/admin/login", "/cliente", "/health", "/health/migrations"}

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

# Archivos estáticos que viven en la raíz del build de Vite (`public/` se copia
# a `dist/`): fotos del estudio (/estudio/*.jpg), favicon, icons, manifest,
# robots, fuentes, etc. Son públicos por naturaleza y los sirve el spa_fallback
# de main.py (que ya tiene guard anti-traversal y solo devuelve archivos reales
# de dist/). Sin esto, el auth_middleware los bloquea y redirige a /login → la
# imagen/asset queda roto. Se matchea por extensión (las rutas del SPA son URLs
# limpias sin extensión) y se excluye /api/ para no abrir endpoints de datos.
STATIC_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg", ".ico",
    ".json", ".txt", ".xml", ".webmanifest",
    ".woff", ".woff2", ".ttf", ".otf",
    ".css", ".js", ".map", ".mp4", ".webm", ".pdf",
)



async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if path in PUBLIC_EXACT:
        return await call_next(request)
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)
    if any(path.startswith(p) for p in PUBLIC_API):
        return await call_next(request)
    # Assets estáticos de dist root (no-/api/ con extensión de archivo).
    if not path.startswith("/api/") and path.endswith(STATIC_EXTENSIONS):
        return await call_next(request)

    session = get_session(request)
    if not session:
        if path.startswith("/api/"):
            return JSONResponse({"detail": "No autenticado"}, status_code=401)
        return RedirectResponse("/login")

    return await call_next(request)
