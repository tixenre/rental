#!/usr/bin/env bash
# Levanta backend y frontend en paralelo.
# Uso: ./dev.sh
# Ctrl+C detiene los dos.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Backend ──────────────────────────────────────────────────────────────────
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "→ Creando venv..."
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

echo "→ Backend arrancando en http://localhost:8000 ..."
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# ── Frontend ─────────────────────────────────────────────────────────────────
cd "$ROOT"
echo "→ Frontend arrancando en http://localhost:3000 ..."
npm run dev &
FRONTEND_PID=$!

# ── Cleanup al Ctrl+C ────────────────────────────────────────────────────────
trap "echo ''; echo 'Deteniendo...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

wait
