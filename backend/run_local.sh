#!/usr/bin/env bash
# Levanta el backend localmente apuntando a la BD de Railway.
# Lee DATABASE_URL desde backend/.env.local (gitignored).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "→ Creando venv..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ Instalando dependencias..."
pip install -q -r requirements.txt

echo "→ Probando conexión a la BD..."
python3 - <<'PY'
import os, pathlib
from dotenv import load_dotenv
load_dotenv(pathlib.Path(__file__).parent / ".env.local")
import psycopg2
url = os.environ["DATABASE_URL"]
print(f"Conectando a {url.split('@')[1]}...")
conn = psycopg2.connect(url, connect_timeout=10)
cur = conn.cursor()
cur.execute("SELECT version();")
print("OK:", cur.fetchone()[0][:60])
conn.close()
PY

echo "→ Levantando uvicorn en http://localhost:8000 ..."
exec uvicorn main:app --reload --port 8000
