"""
Rambla Rental API — FastAPI + PostgreSQL
Run: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from database import init_db, FRONT, FRONT_NEW
from routes.equipos          import router as equipos_router
from routes.alquileres       import router as alquileres_router
from routes.clientes         import router as clientes_router
from routes.estadisticas     import router as estadisticas_router
from routes.dashboard        import router as dashboard_router
from routes.auth             import router as auth_router
from routes.settings         import router as settings_router
from routes.cliente_portal   import router as cliente_portal_router
from middleware          import auth_middleware

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Rambla Rental API", version="2.0")

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Frontend clásico (admin, login, etc.) — opcional, solo si existe
if FRONT.exists():
    app.mount("/static", StaticFiles(directory=str(FRONT)), name="static")

# Nuevo frontend (Vite SPA)
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
app.include_router(cliente_portal_router)

# ── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}

# ── Páginas ──────────────────────────────────────────────────────────────────

def _serve_or_spa(static_path):
    """Sirve un archivo del frontend clásico si existe; si no, sirve la SPA."""
    if FRONT.exists() and static_path.exists():
        return FileResponse(str(static_path))
    new_index = FRONT_NEW / "index.html"
    if new_index.exists():
        return FileResponse(str(new_index))
    return RedirectResponse("/")


@app.get("/", include_in_schema=False)
def root():
    new_index = FRONT_NEW / "index.html"
    if new_index.exists():
        return FileResponse(str(new_index))
    if FRONT.exists() and (FRONT / "index.html").exists():
        return FileResponse(FRONT / "index.html")
    return {"message": "Rambla Rental API"}


@app.get("/login", include_in_schema=False)
def login_page():
    return _serve_or_spa(FRONT / "login.html")


@app.get("/admin", include_in_schema=False)
def admin():
    return _serve_or_spa(FRONT / "admin.html")


@app.get("/equipo/{id}", include_in_schema=False)
def equipo_page(id: int):
    return _serve_or_spa(FRONT / "equipo.html")


@app.get("/cliente", include_in_schema=False)
def cliente_login_page():
    return _serve_or_spa(FRONT / "cliente.html")


@app.get("/cliente/portal", include_in_schema=False)
def cliente_portal_page():
    return _serve_or_spa(FRONT / "cliente" / "portal.html")


@app.get("/cliente/registro", include_in_schema=False)
def cliente_registro_page():
    return _serve_or_spa(FRONT / "cliente" / "registro.html")


# ── SPA catch-all ─────────────────────────────────────────────────────────────
from fastapi import Request as FastAPIRequest


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    new_index = FRONT_NEW / "index.html"
    if new_index.exists():
        return FileResponse(str(new_index))
    if FRONT.exists() and (FRONT / "index.html").exists():
        return FileResponse(FRONT / "index.html")
    return {"message": "Not found"}


# ── Init DB ──────────────────────────────────────────────────────────────────

try:
    init_db()
    print("✅ BD PostgreSQL inicializada")
except Exception as e:
    print(f"⚠️  No se pudo inicializar BD: {e}")
    print("   La app continuará ejecutándose. Verifica DATABASE_URL.")
