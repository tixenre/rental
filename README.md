# Rambla Rental

Plataforma de alquiler de equipos audiovisuales. Catálogo público, portal de cotización para clientes, y back-office completo para administrar pedidos, stock, pagos y documentos (cotizaciones, albaranes, contratos).

## Stack

- **Frontend** — React 19 + Vite + TanStack Router + TanStack Query + Tailwind CSS v4 + shadcn/Radix UI
- **Backend** — FastAPI + psycopg2 + PostgreSQL (pool de conexiones)
- **Auth** — Google OAuth (admin + portal cliente) vía Supabase Auth
- **Storage** — Cloudflare R2 (S3-compatible) para fotos de equipos
- **Deploy** — Railway (backend + frontend en un mismo servicio)

## Setup local

Requisitos: Node ≥ 20, Python ≥ 3.11, PostgreSQL local o acceso a una BD remota.

```bash
# 1. Variables de entorno
cp .env.example backend/.env.local
# Editar backend/.env.local con tus credenciales (SECRET_KEY, DATABASE_URL, Google OAuth, R2)

# 2. Dependencias frontend
npm install  # o bun install

# 3. Levantar backend + frontend (paralelo, Ctrl+C los baja a los dos)
./dev.sh
```

- Frontend dev: http://localhost:3000
- Backend dev: http://localhost:8000
- El proxy de Vite reenvía `/api` y `/auth` al backend.

Si querés correr solo el backend apuntando a la BD de Railway:

```bash
cd backend && ./run_local.sh
```

## Estructura del repo

```
.
├── backend/              FastAPI + PostgreSQL
│   ├── main.py           Entrypoint Uvicorn + monta routes
│   ├── database.py       Pool de conexiones + wrapper sqlite3-like
│   ├── routes/           Endpoints por dominio (alquileres, equipos, clientes, ...)
│   ├── services/         Lógica compartida (PDF, R2 storage, etc.)
│   └── pdf.py            Generación de cotizaciones, albaranes, contratos
├── src/                  Frontend React + Vite
│   ├── routes/           Páginas (TanStack Router file-based)
│   ├── components/       UI compartida (admin + público + shadcn)
│   ├── lib/              API clients, helpers, hooks
│   └── integrations/     Supabase auth, R2, etc.
├── docs/                 Documentación interna (ver abajo)
├── dist/                 Frontend compilado (no editar)
├── dev.sh                Levanta backend + frontend
└── Dockerfile            Build de producción (Railway)
```

## Novedades (changelog)

El feed de "Novedades" en `/admin/novedades` se alimenta de `src/data/changelog.ts`. Cada entrada se agrega **manualmente** en el mismo PR que la cambio — el feed está **curado** (no es 1:1 con los commits).

Para no olvidarse de agregar entrada al mergear PRs:

```bash
npm run changelog:draft         # default: últimos 30 PRs
npm run changelog:draft -- --limit 50
```

El script lista los PRs mergeados que **no están** en `changelog.ts` con un draft TS listo para pegar al inicio del array. Después editás `title` y `body` para que estén en lenguaje claro al usuario (no técnico), y commiteás.

Requiere `gh` CLI autenticado.

## Migraciones (Alembic)

Schema versionado. El `backend/database.py::init_db()` sigue creando tablas con `CREATE IF NOT EXISTS` para BD nuevas; Alembic registra y aplica cambios incrementales en BD existentes.

```bash
# Crear una migración nueva (cambio de schema)
cd backend
alembic revision -m "agregar columna foo a equipos"
# Editar el archivo generado en backend/migrations/versions/

# Aplicar migraciones pendientes (BD local)
alembic upgrade head

# Ver estado actual
alembic current

# Listar migraciones
alembic history
```

En **producción**, las migraciones corren automáticamente al arrancar la app (`main.py::init_db_bg`).

**No usamos autogenerate** porque el proyecto no tiene modelos SQLAlchemy. Las migraciones se escriben a mano con `op.execute("SQL...")` o helpers de `alembic.op`.

## Tests

```bash
# Backend (pytest)
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt   # primera vez
python -m pytest tests/                # corre todo
python -m pytest tests/test_ssrf.py    # un archivo
python -m pytest -k "fecha" -v         # filtrar por nombre
```

Los tests están marcados con `@pytest.mark.unit` (sin DB, sin red) y eventualmente `@pytest.mark.integration` (con BD efímera — pendiente). Hoy son todos `unit`.

CI corre `pytest` automáticamente en cada PR a `main` (job `python-tests` en `.github/workflows/ci.yml`).

## Workflow de desarrollo

Cada cambio va por PR contra `main` con `Closes #N` linkeando un Issue. Branch corta por PR (`claude/<descripcion>` para sesiones con Claude). Después de mergear: borrar la branch local y remota.

Detalle del flow + decisiones del proyecto en [`MANIFIESTO.md`](MANIFIESTO.md). Protocolo de auditoría + PRs en [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md).

## Tracking (GitHub Issues)

Labels: `bug` / `feature` / `design` / `security` + `priority:critical|high|medium|low`.

```bash
gh issue list --state open                                # ver todo abierto
gh issue create --title "..." --label bug,priority:high  # reportar
```

## Deploy

Producción corre en Railway. Detalle de variables, build, troubleshooting:
[docs/DEPLOY_RAILWAY.md](docs/DEPLOY_RAILWAY.md).

## Docs

- [MANIFIESTO.md](MANIFIESTO.md) — contexto del proyecto para sesiones con Claude (workflow, decisiones, estado actual)
- [docs/PROTOCOLO.md](docs/PROTOCOLO.md) — protocolo de auditoría + PRs
- [docs/DEPLOY_RAILWAY.md](docs/DEPLOY_RAILWAY.md) — setup de Railway
- [docs/DISEÑO_SPECS.md](docs/DISEÑO_SPECS.md) — diseño del sistema de specs por categoría
- [docs/DATASET_ILUMINACION.md](docs/DATASET_ILUMINACION.md) — dataset curado de luces + workflow seed por categoría
- [docs/MEJORAS.md](docs/MEJORAS.md) — backlog histórico (deprecated, referencia)
- [docs/BUGS.md](docs/BUGS.md) — histórico de bugs (mayo 2026, referencia)
