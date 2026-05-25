#!/usr/bin/env bash
# e2e-stack.sh — levanta Postgres + backend para correr E2E REALES (no mockeados)
# o QA en entornos sin base (contenedores efímeros, CI con root).
#
# A diferencia de dev.sh (que asume Postgres + env ya configurados), esto:
#   1. arranca el cluster Postgres local,
#   2. crea la DB `rambla_rental` y setea el password,
#   3. exporta DATABASE_URL + SECRET_KEY,
#   4. arranca el backend (que corre migraciones + init_db al boot),
#   5. opcionalmente siembra datos demo (--seed).
#
# Uso:
#   sudo scripts/e2e-stack.sh            # backend en :8000
#   sudo scripts/e2e-stack.sh --seed     # + 1 equipo y 1 reserva de ejemplo
#
# Después, en otra terminal: `npm run dev` + `npx playwright test`.
# Requiere root (arranca Postgres) y postgresql-16 instalado.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 1. Postgres
service postgresql start 2>/dev/null || pg_ctlcluster 16 main start 2>/dev/null || true
sleep 1
su - postgres -c "psql -tAc \"ALTER USER postgres PASSWORD 'postgres'\"" >/dev/null 2>&1 || true
su - postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='rambla_rental'\"" 2>/dev/null | grep -q 1 \
  || su - postgres -c "createdb rambla_rental" >/dev/null 2>&1 || true

# 2. Env (no pisa si ya vienen seteadas)
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost/rambla_rental}"
export SECRET_KEY="${SECRET_KEY:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')}"

# 3. Deps backend (PyJWT viene del sistema en algunos entornos → se ignora)
cd "$ROOT/backend"
pip install -q -r requirements.txt --ignore-installed PyJWT >/dev/null 2>&1 || \
  pip install -q -r requirements.txt >/dev/null 2>&1 || true

# 4. Seed opcional (idempotente-ish: corre después de que el backend creó el schema)
if [ "${1:-}" = "--seed" ]; then
  # Arrancamos el backend en background sólo para crear el schema, lo paramos y sembramos.
  DATABASE_URL="$DATABASE_URL" SECRET_KEY="$SECRET_KEY" uvicorn main:app --port 8000 >/tmp/e2e-backend-init.log 2>&1 &
  INIT_PID=$!
  for _ in $(seq 1 30); do curl -sf http://127.0.0.1:8000/api/categorias >/dev/null 2>&1 && break; sleep 1; done
  kill "$INIT_PID" 2>/dev/null || true
  sleep 1
  PGPASSWORD=postgres psql -h 127.0.0.1 -U postgres -d rambla_rental >/dev/null 2>&1 <<'SQL' || true
INSERT INTO equipos (nombre, cantidad, precio_jornada, visible_catalogo, estado)
SELECT 'Demo Cam (stock 1)', 1, 10000, 1, 'operativo'
WHERE NOT EXISTS (SELECT 1 FROM equipos WHERE nombre='Demo Cam (stock 1)');
INSERT INTO alquileres (cliente_nombre, estado, fecha_desde, fecha_hasta, numero_pedido, monto_total)
SELECT 'Demo Reserva', 'confirmado', '2026-06-15T09:00:00', '2026-06-17T09:00:00', nextval('numero_pedido_seq'), 20000
WHERE NOT EXISTS (SELECT 1 FROM alquileres WHERE cliente_nombre='Demo Reserva');
INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, precio_jornada, subtotal)
SELECT a.id, e.id, 1, 10000, 20000
FROM alquileres a, equipos e
WHERE a.cliente_nombre='Demo Reserva' AND e.nombre='Demo Cam (stock 1)'
  AND NOT EXISTS (SELECT 1 FROM alquiler_items i WHERE i.pedido_id=a.id AND i.equipo_id=e.id);
SQL
  echo "→ Seed demo listo (equipo + reserva 15-17 jun 2026)."
fi

# 5. Backend (foreground)
echo "→ Backend en http://localhost:8000  ·  DATABASE_URL=$DATABASE_URL"
exec env DATABASE_URL="$DATABASE_URL" SECRET_KEY="$SECRET_KEY" uvicorn main:app --port 8000
