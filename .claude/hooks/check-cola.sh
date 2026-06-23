#!/bin/bash
# Check-in proactivo de la cola — SessionStart
# Si .claude/cola-state.json no existe o last-run > 7 días, imprime un recordatorio.
python3 - <<'EOF'
import json, sys
from pathlib import Path
from datetime import datetime, timezone

state_file = Path('.claude/cola-state.json')
if not state_file.exists():
    print("⚠  Cola: sin registro de última revisión — corré /cola para inicializar el check-in.")
    sys.exit(0)

try:
    data = json.loads(state_file.read_text())
    last_run = datetime.fromisoformat(data.get('last-run', '').replace('Z', '+00:00'))
    days = (datetime.now(timezone.utc) - last_run).days
    if days > 7:
        print(f"⚠  Cola: no se revisa hace {days} días → corré /cola")
except Exception:
    print("⚠  Cola: no se pudo leer cola-state.json → corré /cola")
EOF
