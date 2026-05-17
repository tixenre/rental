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
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Configurar logging ANTES de importar cualquier módulo del proyecto
# (algunos crean loggers a nivel de módulo).
from logging_config import setup_logging, request_id_var
setup_logging()

# ── Sentry (error tracking) ──────────────────────────────────────────────────
# Solo activo si SENTRY_DSN está seteado — dev/CI no lo necesitan.
_sentry_dsn = os.environ.get("SENTRY_DSN")
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=os.environ.get("RAILWAY_ENVIRONMENT", "production"),
        send_default_pii=False,
    )

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
from routes.specs_observatorio import router as specs_observatorio_router
from routes.unidades         import router as unidades_router
from routes.changelog        import router as changelog_router
from routes.seo              import router as seo_router
from routes.inventario       import router as inventario_router
from middleware          import auth_middleware

logger = logging.getLogger(__name__)

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Rambla Rental API", version="2.0")

# ── Rate limiting (#58) ──────────────────────────────────────────────────────
# In-memory: sirve para 1 instancia de Railway. Si se escala a multi-instancia
# o se agrega Redis, cambiar storage_uri a "redis://..." (slowapi lo soporta).
#
# Defaults: 200 requests/minuto por IP. Endpoints sensibles (auth, cotización)
# tienen rate más estricto via @limiter.limit("...") en cada handler.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    headers_enabled=True,  # devuelve X-RateLimit-* en cada response
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


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
app.include_router(specs_observatorio_router, prefix="/api")
app.include_router(unidades_router,       prefix="/api")
app.include_router(changelog_router,      prefix="/api")
app.include_router(inventario_router,     prefix="/api/admin")
app.include_router(seo_router)  # /sitemap.xml (sin prefijo /api — debe estar en root)
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

def _run_alembic_migrations() -> None:
    """Corre `alembic upgrade head` en background al arrancar.

    Falla silenciosamente con log de error — la app sigue arrancando. Crítico
    para no romper deploys si una migración tiene un bug.

    Idempotente: en BD pre-Alembic, el baseline es no-op + agrega la tabla
    `alembic_version`. Próximos arranques solo aplican migraciones nuevas.
    """
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    backend_root = Path(__file__).resolve().parent
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "migrations"))
    command.upgrade(cfg, "head")


def init_db_bg():
    try:
        init_db()
        logger.info("BD PostgreSQL inicializada")
    except Exception as e:
        logger.error("No se pudo inicializar BD: %s. La app continuará — verificar DATABASE_URL.", e, exc_info=True)
        return  # Si init_db falló, no tiene sentido correr alembic.

    try:
        _run_alembic_migrations()
        logger.info("Migraciones Alembic al día")
    except Exception as e:
        logger.error("Falló alembic upgrade: %s. La app sigue arrancando — revisar manualmente.", e, exc_info=True)

    # Seed de specs DESPUÉS de alembic — corre el registry seeder por cada
    # categoría declarada en backend/specs/registry.py. Idempotente.
    try:
        from database import get_db
        from seeds.registry_seeder import seed_all_categorias
        conn = get_db()
        try:
            result = seed_all_categorias(conn)
            conn.commit()
            total_specs = sum(
                r["stats"].get("specs_creadas", 0)
                for r in result["categorias"].values()
            )
            if total_specs > 0:
                logger.info("Registry seedeado: %d specs en %d categorías",
                            total_specs, len(result["categorias"]))
        finally:
            conn.close()
    except Exception as e:
        logger.warning("Registry seeder falló (no crítico): %s", e)

    # Per-cat seeds: pueblan `equipo_specs` (valores) y sub-cats dinámicas
    # (Monturas, diámetros) que el registry no declara. Idempotentes:
    # ON CONFLICT (equipo_id, spec_def_id) DO UPDATE en equipo_specs,
    # docs/equipos_match.json preserva equipo.id para FKs de pedidos.
    # Sin esto, la migración c1f9e5d3b7a8 (que wipea equipo_specs) deja la
    # DB con specs vacíos hasta que un humano corra `python -m backend.seeds.*`
    # a mano en la shell de Railway.
    _PER_CAT_SEEDS = [
        ("camaras",     "seed_camaras"),
        ("lentes",      "seed_lentes"),
        ("adaptadores", "seed_adaptadores"),
        ("filtros",     "seed_filtros"),
        ("iluminacion", "seed_iluminacion"),
    ]
    for modname, fnname in _PER_CAT_SEEDS:
        try:
            from database import get_db
            mod = __import__(f"seeds.{modname}", fromlist=[fnname])
            fn = getattr(mod, fnname)
            conn = get_db()
            try:
                stats = fn(conn)
                conn.commit()
                if isinstance(stats, dict) and "error" not in stats:
                    logger.info(
                        "Seed %s OK: +%d equipos, ~%d actualizados, %d specs",
                        modname,
                        stats.get("equipos_creados", 0),
                        stats.get("equipos_actualizados", 0),
                        stats.get("equipo_specs_insertados", 0),
                    )
                elif isinstance(stats, dict) and "error" in stats:
                    logger.warning("Seed %s skip: %s", modname, stats["error"])
            finally:
                conn.close()
        except Exception as e:
            logger.warning("Seed %s falló (no crítico, sigue resto): %s", modname, e)

    # Auto-run del ranking si nunca corrió (popularidad_score=0 en todos
    # los equipos). Después de eso, queda en manos del admin desde
    # /admin/settings. Issue #131.
    try:
        _maybe_run_initial_ranking()
    except Exception as e:
        logger.error("Falló cálculo inicial de ranking: %s. La app sigue. Recalcular manual desde /admin/settings.", e, exc_info=True)


def _maybe_run_initial_ranking() -> None:
    """Corre el cálculo de ranking SI ningún equipo tiene
    ranking_actualizado seteado (nunca se corrió). Después de la primera
    vez, queda en manos del admin re-correrlo desde /admin/settings.
    """
    from database import get_db
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM equipos WHERE ranking_actualizado IS NOT NULL"
        ).fetchone()
        ya_corrio = int(row["n"] or 0) > 0
        if ya_corrio:
            logger.info("Ranking ya tiene datos previos — se saltea el cálculo inicial.")
            return

        logger.info("Corriendo cálculo inicial de ranking (primera vez)...")
        from services.ranking_service import recalcular_ranking_todos
        result = recalcular_ranking_todos(conn, dry_run=False)
        logger.info(
            "Ranking inicial OK: %d equipos · %d categorías · %d marcas actualizados",
            len(result.get("cambios", [])),
            len(result.get("cambios_categorias", [])),
            len(result.get("cambios_marcas", [])),
        )
    finally:
        conn.close()


db_init_thread = threading.Thread(target=init_db_bg, daemon=True)
db_init_thread.start()
