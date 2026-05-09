FROM python:3.11-slim

WORKDIR /app

# Sistema base (sin git — el frontend se buildea desde el contexto local)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Bun (para buildear el frontend)
RUN curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.bun/bin:$PATH"

# Directorio para volumen persistente (datos)
RUN mkdir -p /app/backend/data

# Dependencias Python (capa cacheada)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Playwright + Chromium (generación de PDFs)
RUN playwright install --with-deps chromium

# Dependencias frontend (capa cacheada)
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# Copiar todo el código fuente y buildear el frontend
COPY . .
RUN bun run build
# → produce /app/dist/ con index.html y assets/

# Healthcheck para Railway
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Iniciar el servidor FastAPI
CMD ["sh", "-c", "cd backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
