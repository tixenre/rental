#!/bin/bash
# Check-in proactivo de la cola de pendientes — SessionStart
# Si .claude/pendientes-state.json no existe o last-run > 7 días, imprime un recordatorio.
python3 - <<'EOF'
import json, sys
from pathlib import Path
from datetime import datetime, timezone

state_file = Path('.claude/pendientes-state.json')
if not state_file.exists():
    print("⚠  Pendientes: sin registro de última revisión — corré /pendientes para inicializar el check-in.")
    sys.exit(0)

try:
    data = json.loads(state_file.read_text())
    last_run = datetime.fromisoformat(data.get('last-run', '').replace('Z', '+00:00'))
    days = (datetime.now(timezone.utc) - last_run).days
    if days > 7:
        print(f"⚠  Pendientes: no se revisa hace {days} días → corré /pendientes")
except Exception:
    print("⚠  Pendientes: no se pudo leer pendientes-state.json → corré /pendientes")
EOF
