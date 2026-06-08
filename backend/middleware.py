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

# Prefijos públicos de SOLO LECTURA — el catálogo anónimo los consume por GET.
# Sus endpoints de ESCRITURA viven bajo /api/admin/... con require_admin; acá se
# eximen únicamente para GET/HEAD para que una escritura anónima bajo el mismo
# prefijo (regresión tipo el CRUD de /api/equipos) caiga igual en el chequeo de
# sesión. NO sustituye al require_admin por handler — es defensa en profundidad.
PUBLIC_API_READONLY = (
    "/api/equipos",
    "/api/categorias",
    "/api/etiquetas",
    "/api/marcas",       # lista de marcas: dato público del catálogo (hermano de /api/categorias).
    "/api/disponibilidad",
    # Config pública del sitio. Sólo GET; cada handler valida adentro lo suyo:
    #  · GET /api/settings/{key} sirve sin sesión SOLO las keys de
    #    PUBLIC_SETTINGS_KEYS (settings.py); el resto exige sesión en el handler.
    #  · GET /api/settings (lista) devuelve el subconjunto público a anónimos y
    #    todo a una sesión admin (gate fino en el handler).
    #  · /api/analytics-config devuelve el GA4 id (no secreto) y gatea por entorno.
    "/api/settings",
    "/api/analytics-config",
)

# Prefijos públicos que aceptan POST a propósito (cada uno valida adentro lo suyo).
PUBLIC_API_ANY = (
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
    # Lecturas públicas del catálogo: solo GET/HEAD se eximen sin sesión. Una
    # escritura bajo el mismo prefijo NO se exime (cae al guard de sesión abajo,
    # y el handler además exige require_admin).
    if request.method in ("GET", "HEAD") and any(path.startswith(p) for p in PUBLIC_API_READONLY):
        return await call_next(request)
    if any(path.startswith(p) for p in PUBLIC_API_ANY):
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
