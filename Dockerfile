# check=skip=SecretsUsedInArgOrEnv
# El linter dispara porque ve "KEY" en VITE_SUPABASE_PUBLISHABLE_KEY, pero
# las VITE_* son públicas por diseño: Vite las inlinea en el JS del frontend
# que se sirve al navegador. La anon key de Supabase es pensada para estar
# expuesta — la seguridad la dan las RLS policies, no esconder la key.

# ── Stage 1: build del frontend (Vite SPA) ───────────────────────────────
# Imagen oficial de Bun (más chica y rápida que instalar bun via curl).
# Esta etapa se descarta — solo se copia /app/dist al runtime.
FROM oven/bun:1 AS frontend
WORKDIR /app

# Variables públicas que Vite inlinea en el bundle.
# (Ver nota al tope sobre SecretsUsedInArgOrEnv: estos no son secretos).
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_PUBLISHABLE_KEY
ARG VITE_SUPABASE_PROJECT_ID
ARG VITE_API_URL
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_PUBLISHABLE_KEY=$VITE_SUPABASE_PUBLISHABLE_KEY
ENV VITE_SUPABASE_PROJECT_ID=$VITE_SUPABASE_PROJECT_ID
ENV VITE_API_URL=$VITE_API_URL

# Deps primero — capa cacheada mientras no cambien package.json/bun.lock.
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# Después código y config — capa que se invalida en cada cambio de UI.
COPY vite.config.ts tsconfig.json index.html ./
COPY public/ ./public/
COPY src/ ./src/
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
COPY --from=frontend /app/dist ./dist

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "cd /app/backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
