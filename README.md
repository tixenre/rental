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

Solo dos branches long-lived:

- `bugs` → arreglos de bugs
- `features` → features nuevas

Cada cambio va por PR contra `main` con `Closes #N` linkeando un Issue.
Detalle completo en [docs/PROTOCOLO.md](docs/PROTOCOLO.md).

```bash
git checkout bugs                       # o features
git pull origin main --rebase           # traer lo último de main
# ... cambios ...
git push origin bugs
gh pr create --base main --head bugs    # PR con "Closes #N"
```

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

- [docs/PROTOCOLO.md](docs/PROTOCOLO.md) — protocolo de auditoría + PRs
- [docs/DEPLOY_RAILWAY.md](docs/DEPLOY_RAILWAY.md) — setup de Railway
- [docs/DISEÑO_SPECS.md](docs/DISEÑO_SPECS.md) — diseño del sistema de specs por categoría
- [docs/MEJORAS.md](docs/MEJORAS.md) — ideas de mejora (impacto/esfuerzo)
- [docs/BUGS.md](docs/BUGS.md) — histórico de bugs (mayo 2026, referencia)
