FROM python:3.11-slim

WORKDIR /app

# -- Sistema base --
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    unzip \
    git \
    && rm -rf /var/lib/apt/lists/*

# -- Node.js (para buildear el frontend) --
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:$PATH"

# -- Directorio para volumen persistente (BD + datos) --
RUN mkdir -p /app/backend/data

# -- Copiar código fuente --
COPY package.json bun.lock vite.config.ts tsconfig.json index.html ./
COPY src/ ./src/
COPY backend/ ./backend/

# -- Dependencias Python --
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -- Playwright + Chromium (necesario para PDF generation) --
# RUN playwright install --with-deps chromium
# NOTA: Deshabilitado para ahorrar memoria en Railway. Si se necesita, descomentar.

# -- Build del frontend (Vite SPA) --
RUN bun install
RUN bun run build

# -- Healthcheck para Railway --
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# -- Comando para iniciar --
CMD ["sh", "-c", "cd /app/backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
