# ── Stage 1: build del frontend (Vite SPA) ───────────────────────────────
# Imagen oficial de Bun (más chica y rápida que instalar bun via curl).
# Esta etapa se descarta — solo se copia /app/dist al runtime.
# Versión PINEADA a propósito: `oven/bun:1` flota a la última 1.x y una bun
# nueva puede recalcular el lockfile distinto y romper `--frozen-lockfile`.
# Debe coincidir con la bun que generó bun.lock; bumpear = regenerar el lock.
FROM oven/bun:1.3.13 AS frontend
WORKDIR /app

# Variables públicas que Vite inlinea en el bundle.
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_PUBLISHABLE_KEY
ARG VITE_SUPABASE_PROJECT_ID
ARG VITE_API_URL
ARG VITE_SENTRY_DSN
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_PUBLISHABLE_KEY=$VITE_SUPABASE_PUBLISHABLE_KEY
ENV VITE_SUPABASE_PROJECT_ID=$VITE_SUPABASE_PROJECT_ID
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN

# Deps primero — capa cacheada mientras no cambien package.json/bun.lock.
COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile

# Después código y config — capa que se invalida en cada cambio de UI.
COPY frontend/vite.config.ts frontend/tsconfig.json frontend/index.html ./
COPY frontend/public/ ./public/
COPY frontend/src/ ./src/
# dev/ solo existe en esta etapa de build (se descarta con la imagen frontend).
# Vite carga su config con esbuild, que resuelve estáticamente todos los
# imports — incluso los dinámicos — antes de ejecutar. Sin este COPY, el
# import condicional de ./dev/api-fixtures-plugin falla aunque no se ejecute.
COPY frontend/dev/ ./dev/
RUN bun run build

# ── Stage 2: runtime (Python + Chromium) ─────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# curl para healthcheck. gcc no hace falta — todas las deps Python tienen
# wheels precompilados (psycopg2-binary, Pillow, pydantic, cryptography).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps primero — capa cacheada mientras no cambie requirements.txt.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright + Chromium (300-400 MB). Sin cache mount: el binario tiene que
# quedar en la capa para que esté disponible en runtime. Capa cacheada
# mientras no cambie requirements.txt — que es la mayoría de los deploys.
RUN playwright install --with-deps chromium

# Directorio para volumen persistente de Railway (BD SQLite legacy, datos).
RUN mkdir -p /app/backend/data

# Código del backend y dist del frontend al final — lo que cambia más seguido.
COPY backend/ ./backend/
# Los parsers determinísticos (lentes_parser, camaras_parser, iluminacion_parser,
# iluminacion_normalizar) viven en tools/ y son importados en runtime por los
# extractores del backend via sys.path. Sin esta línea, el upload de HTML falla
# con "No module named 'lentes_parser'" en producción.
COPY tools/ ./tools/
# Fuentes de marca para los PDFs: `pdf_templates._fonts_css()` las embebe en
# runtime desde `frontend/src/assets/fonts` (FONTS_DIR = backend/../frontend/src/
# assets/fonts). El runtime NO trae todo `frontend/src/` (solo el `dist`
# buildeado), así que copiamos explícitamente las fuentes — sin esto los
# documentos PDF saldrían con la tipografía del sistema en vez de la de Rambla
# (degrada silencioso, no rompe).
COPY frontend/src/assets/fonts/ ./frontend/src/assets/fonts/
COPY --from=frontend /app/dist ./frontend/dist

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "cd /app/backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
