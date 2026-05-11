"""
Rambla Rental API — FastAPI + PostgreSQL
Run: uvicorn main:app --reload --port 8000
"""

import logging
import os
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Configurar logging ANTES de importar cualquier módulo del proyecto
# (algunos crean loggers a nivel de módulo).
from logging_config import setup_logging, request_id_var
setup_logging()

from database import init_db, FRONT, FRONT_NEW
from routes.equipos          import router as equipos_router
from routes.alquileres       import router as alquileres_router
from routes.clientes         import router as clientes_router
from routes.estadisticas     import router as estadisticas_router
from routes.dashboard        import router as dashboard_router
from routes.auth             import router as auth_router
from routes.settings         import router as settings_router
from routes.cliente_portal   import router as cliente_portal_router
from routes.marcas           import router as marcas_router
from routes.specs            import router as specs_router
from routes.changelog        import router as changelog_router
from middleware          import auth_middleware

logger = logging.getLogger(__name__)

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Rambla Rental API", version="2.0")


async def request_id_middleware(request: Request, call_next):
    """Inyecta un request_id único en context para que los logs lo incluyan.

    Si el cliente envía un header X-Request-Id, lo respeta (útil para tracear
    desde Sentry/Cloudflare). Si no, generamos un UUID4.
    """
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        return response
    finally:
        request_id_var.reset(token)

# Orígenes permitidos para CORS con credenciales (cookie de sesión).
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://localhost:8000",
    ).split(",") if o.strip()
]

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=request_id_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Montar el frontend clásico solo si existe (no existe en el monorepo rental-refine)
if FRONT.exists():
    app.mount("/static", StaticFiles(directory=str(FRONT)), name="static")

# Nuevo frontend (Vite SPA — rental-refine)
if FRONT_NEW.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONT_NEW / "assets")), name="assets")

# ── Routers ──────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(equipos_router,        prefix="/api")
app.include_router(alquileres_router,     prefix="/api")
app.include_router(clientes_router,       prefix="/api")
app.include_router(estadisticas_router,   prefix="/api")
app.include_router(dashboard_router,      prefix="/api")
app.include_router(settings_router,       prefix="/api")
app.include_router(marcas_router,         prefix="/api")
app.include_router(specs_router,          prefix="/api")
app.include_router(changelog_router,      prefix="/api")
app.include_router(cliente_portal_router)

# ── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health", include_in_schema=False)
def health():
    """Health check endpoint para Railway."""
    return {"status": "ok"}

# ── Páginas ──────────────────────────────────────────────────────────────────

def _serve_frontend(path: str = "index.html"):
    """Helper: sirve desde FRONT_NEW (Vite SPA) o FRONT (clásico) si existe."""
    new_file = FRONT_NEW / path
    if new_file.exists():
        return FileResponse(str(new_file))
    classic_file = FRONT / path
    if classic_file.exists():
        return FileResponse(str(classic_file))
    spa_index = FRONT_NEW / "index.html"
    if spa_index.exists():
        return FileResponse(str(spa_index))
    return JSONResponse({"error": "Frontend not built"}, status_code=503)

@app.get("/", include_in_schema=False)
def root():
    return _serve_frontend("index.html")

@app.get("/login", include_in_schema=False)
def login_page():
    # El login del admin vive en el SPA en /admin/login.
    return RedirectResponse("/admin/login", status_code=307)

@app.get("/admin", include_in_schema=False)
def admin():
    return _serve_frontend("admin.html")

@app.get("/equipo/{id}", include_in_schema=False)
def equipo_page(id: int):
    return _serve_frontend("index.html")

@app.get("/cliente", include_in_schema=False)
def cliente_login_page():
    return _serve_frontend("cliente.html")

@app.get("/cliente/portal", include_in_schema=False)
def cliente_portal_page():
    return _serve_frontend("cliente/portal.html")

@app.get("/cliente/registro", include_in_schema=False)
def cliente_registro_page():
    return _serve_frontend("cliente/registro.html")

# ── SPA catch-all: rutas del nuevo frontend (TanStack Router) ────────────────
# Debe ir AL FINAL para no interceptar rutas de API ni páginas de admin.

@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    """
    Devuelve index.html del nuevo frontend para cualquier ruta no reconocida.
    TanStack Router maneja el enrutamiento del lado del cliente.
    Las rutas /api/* y /static/* se capturan antes que esta.
    """
    return _serve_frontend("index.html")

# ── Init DB (non-blocking) ───────────────────────────────────────────────────
# Initialize DB in background thread to not block app startup / healthcheck

def init_db_bg():
    try:
        init_db()
        logger.info("BD PostgreSQL inicializada")
    except Exception as e:
        logger.error("No se pudo inicializar BD: %s. La app continuará — verificar DATABASE_URL.", e, exc_info=True)

db_init_thread = threading.Thread(target=init_db_bg, daemon=True)
db_init_thread.start()
