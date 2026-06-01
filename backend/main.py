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
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Configurar logging ANTES de importar cualquier módulo del proyecto
# (algunos crean loggers a nivel de módulo).
from logging_config import setup_logging, request_id_var
setup_logging()

from config import settings

# ── Sentry (error tracking) ──────────────────────────────────────────────────
# Solo activo si SENTRY_DSN está seteado — dev/CI no lo necesitan.
_sentry_dsn = settings.SENTRY_DSN
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=settings.RAILWAY_ENVIRONMENT or "production",
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
from routes.unidades         import router as unidades_router
from routes.seo              import router as seo_router
from routes.inventario       import router as inventario_router
from routes.email_templates  import router as email_templates_router
from routes.dataio           import router as dataio_router
from routes.estudio          import router as estudio_router
from middleware          import auth_middleware

logger = logging.getLogger(__name__)

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Rambla Rental API", version="2.0")

# ── Rate limiting (#58) ──────────────────────────────────────────────────────
# El limiter vive en `rate_limit.py` (compartido con los routers que usan
# @limiter.limit en handlers sensibles, sin ciclos de import).
from rate_limit import limiter
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
ALLOWED_ORIGINS = settings.frontend_origins

# Hardening pre-launch (#503): CORS con credenciales + localhost/wildcard en
# prod es peligroso. Rompemos el boot explícitamente para que no pase callado.
if os.getenv("RAILWAY_ENVIRONMENT"):
    _inseguros = [o for o in ALLOWED_ORIGINS if "localhost" in o or "127.0.0.1" in o or o == "*"]
    if _inseguros:
        raise RuntimeError(
            f"CORS inseguro en producción: FRONTEND_ORIGINS incluye {_inseguros}. "
            "Revisá la env var en Railway (no debe tener localhost ni '*')."
        )

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

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
app.include_router(unidades_router,       prefix="/api")
app.include_router(inventario_router,     prefix="/api/admin")
app.include_router(email_templates_router, prefix="/api")
app.include_router(dataio_router,         prefix="/api")
app.include_router(estudio_router,        prefix="/api")
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

    Antes de caer al index.html, sirve archivos estáticos reales que viven en
    la raíz del build de Vite (`public/` se copia a `dist/`): /estudio/*.jpg,
    /favicon.png, /robots.txt, /icon-512.png, /manifest-admin.json, etc. Sin
    esto, esos assets caen al catch-all y devuelven el HTML del SPA → imagen
    rota. El mount /assets solo cubre dist/assets (bundles hasheados).
    """
    if full_path:
        front_root = FRONT_NEW.resolve()
        candidate = (front_root / full_path).resolve()
        # Guard anti path-traversal: el archivo tiene que vivir dentro de dist/.
        if candidate.is_file() and candidate.is_relative_to(front_root):
            return FileResponse(str(candidate))
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


def _seed_registry() -> None:
    """Persiste el registry de specs (código `backend/specs/`) a la DB.

    Idempotente: solo crea/actualiza `spec_definitions` y
    `categoria_spec_templates` con base en lo declarado en el código.
    Los equipos NO se cargan acá — el flujo activo es vía
    `tools/specs_import_preview.py` → `dataio.cli import`.

    Los seeders por categoría que existían (camaras.py, lentes.py, etc.)
    se eliminaron en Fase C del refactor de specs: eran fallback histórico
    para arrancar ambientes nuevos, hoy reemplazados por dataio.import_all.
    """
    from database import get_db
    try:
        from seeds.registry_seeder import seed_all_categorias
        conn = get_db()
        try:
            result = seed_all_categorias(conn)
            conn.commit()
            total_specs = sum(
                r["stats"].get("specs_creadas", 0)
                for r in result["categorias"].values()
            )
            total_purgadas = sum(
                r["stats"].get("specs_purgadas", 0)
                for r in result["categorias"].values()
            )
            logger.info(
                "Registry seedeado: %d specs en %d categorías (purgadas=%d)",
                total_specs, len(result["categorias"]), total_purgadas,
            )
        except Exception:
            try:
                conn.rollback()
            except Exception:
                logger.warning("cleanup: error en rollback de conexión del seeder", exc_info=True)
            raise
        finally:
            conn.close()
    except Exception as e:
        logger.warning("Registry seeder falló (no crítico): %s", e)


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

    # Registry de specs → DB (idempotente, siempre corre en boot).
    # Persiste spec_definitions + categoria_spec_templates desde el
    # código del registry (`backend/specs/categorias/*.py`). Sin esto,
    # las tablas de specs quedarían vacías.
    try:
        _seed_registry()
    except Exception as e:
        logger.error("Falló _seed_registry: %s. La app sigue.", e, exc_info=True)

    # Catálogo (equipos/categorías/marcas/etc.): si `/data/catalog/`
    # tiene los JSONs versionados, los importa vía dataio. Si no existe,
    # la DB se mantiene como está (los ambientes en producción ya tienen
    # equipos persistidos de boots anteriores; los ambientes nuevos se
    # cargan vía `python -m backend.dataio.cli import` manualmente).
    from database import get_db
    from dataio import orchestrator as dataio_orch

    if dataio_orch.has_catalog_data():
        conn = get_db()
        try:
            stats = dataio_orch.import_all(conn)
            conn.commit()
            total_ins = sum(s.get("inserted", 0) for s in stats.values())
            total_upd = sum(s.get("updated", 0) for s in stats.values())
            logger.info(
                "dataio.import_all OK: +%d inserts, ~%d updates desde /data/catalog/",
                total_ins, total_upd,
            )
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error(
                "dataio.import_all falló: %s. El operador debe arreglar el JSON.",
                e, exc_info=True,
            )
        finally:
            conn.close()
    else:
        logger.info(
            "dataio.import_all: /data/catalog/ vacío o ausente — DB se mantiene "
            "como está. Para cargar equipos nuevos, usar "
            "`python -m backend.dataio.cli import` después de generar JSONs con "
            "`tools/specs_import_preview.py`."
        )

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
