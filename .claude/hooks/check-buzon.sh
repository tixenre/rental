#!/bin/bash
# SessionStart hook — cierre de gobernanza disparado por VOLUMEN del buzón (no por calendario).
# GEMELO de check-pendientes.sh: cuenta un backlog y nudgea. Si docs/PROPUESTAS_SKILLS.md junta
# >= THRESHOLD propuestas PENDIENTES (sin marcar "✅ aplicada"), recordá correr el cierre de
# gobernanza (skill `gobernanza` §6 · /gobernanza).
#
# Sin state file a propósito: recomputa en cada SessionStart, así el aviso PERSISTE hasta que el
# cierre baje el buzón — esa persistencia ES la feature (igual que el aviso de pendientes >7 días).
#
# Corre en terminal (CLI) y desktop de Claude Code, NO en el chat de Mac/iPhone ni web/nube.
# Falla SIEMPRE en silencio (exit 0): un hook nunca debe interrumpir la sesión.

root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$root" 2>/dev/null || exit 0

python3 - <<'EOF'
import re, sys
from pathlib import Path

THRESHOLD = 5  # propuestas pendientes que disparan el cierre (tuneable; se afina con el ritmo real)

f = Path('docs/PROPUESTAS_SKILLS.md')
if not f.exists():
    sys.exit(0)

text = f.read_text()
text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)  # descartar el ejemplo comentado

# Una propuesta = un bloque que arranca con "YYYY-MM-DD ·" a nivel 0 (los ↳/sangrados son sub-notas
# del bloque padre). Pendiente = el bloque no contiene "✅".
entries, cur = [], None
for ln in text.splitlines():
    if re.match(r'^\d{4}-\d{2}-\d{2}\s*·', ln):
        if cur is not None:
            entries.append(cur)
        cur = ln
    elif cur is not None:
        cur += "\n" + ln
if cur is not None:
    entries.append(cur)

pending = sum(1 for e in entries if '✅' not in e)
if pending >= THRESHOLD:
    print(f"⚠  Gobernanza: el buzón juntó {pending} propuestas pendientes (≥{THRESHOLD}) → preguntale al dueño si corrés el cierre de gobernanza (/gobernanza · skill gobernanza §6).")
    print("   Triage del buzón (aprobar/descartar/diferir) + auditoría/ledger/staleness; cada 2 cierres re-derivá los principios. Propone-no-aplica salvo el buzón.")
EOF
exit 0
