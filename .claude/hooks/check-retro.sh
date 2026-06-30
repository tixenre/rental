#!/bin/bash
# Stop hook — retro de iniciativa auto-ruteada (Nivel 1 de "que los evals se usen solos").
# GEMELO de check-governance-review.sh: misma mecánica, distinto target.
#
# Si la rama tocó código de PRODUCTO de forma SUSTANCIAL (no trivial), recordá —UNA vez por
# cambio-set, NO en cada turno— correr el RETRO: la sesión analiza qué rindió y qué no, y REPARTE
# cada aprendizaje a su destino (buzón de skills / memoria / SISTEMA_* / Filosofía). El método vive
# en el skill `gobernanza` (sección "Retro de iniciativa").
#
# Un shell no puede despachar un agente ni preguntarte y esperar: surfacea el recordatorio, y la
# sesión —al verlo— TE PREGUNTA si corrés el retro (sí/no). Vos seguís siendo el gate.
#
# Corre en la TERMINAL (CLI) y el desktop de Claude Code, NO en el chat de Mac/iPhone ni la web/nube.
# Falla SIEMPRE en silencio (exit 0): un hook nunca debe interrumpir la sesión.

# --- Umbral de "no trivial" (generoso: una iniciativa o un bug grande lo superan; un typo no) ---
MIN_FILES=4
MIN_LINES=150

root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$root" 2>/dev/null || exit 0

base="$(git merge-base HEAD origin/dev 2>/dev/null || true)"

# Paths cambiados: lo que la rama agregó vs origin/dev + lo no-commiteado (staged y working).
changed="$( {
  [ -n "$base" ] && git diff --name-only "$base" HEAD 2>/dev/null
  git diff --name-only 2>/dev/null
  git diff --name-only --cached 2>/dev/null
} | sort -u )"

# Solo código de producto (excluye gobernanza por path → cero overlap con el otro hook).
prod="$(printf '%s\n' "$changed" | grep -E '^(backend/|frontend/src/)' || true)"
[ -z "$prod" ] && exit 0

n_files="$(printf '%s\n' "$prod" | grep -c .)"

# Líneas cambiadas en producto (numstat: $1 add, $2 del; binarios '-' se ignoran).
n_lines="$( {
  [ -n "$base" ] && git diff --numstat "$base" HEAD -- backend frontend/src 2>/dev/null
  git diff --numstat -- backend frontend/src 2>/dev/null
  git diff --numstat --cached -- backend frontend/src 2>/dev/null
} | awk '$1 ~ /^[0-9]+$/ && $2 ~ /^[0-9]+$/ { s += $1 + $2 } END { print s+0 }' )"

# No trivial = supera el umbral de archivos O el de líneas. Si no, silencio.
[ "$n_files" -lt "$MIN_FILES" ] && [ "$n_lines" -lt "$MIN_LINES" ] && exit 0

# Dedupe por cambio-set: solo recuerda una vez por lista de archivos de producto (estado gitignored).
state="$root/.claude/.retro-state"
sig="$(printf '%s' "$prod" | cksum 2>/dev/null | cut -d' ' -f1)"
[ -n "$sig" ] && [ "$(cat "$state" 2>/dev/null)" = "$sig" ] && exit 0
[ -n "$sig" ] && printf '%s' "$sig" > "$state" 2>/dev/null || true

echo "⚠ Retro de iniciativa — esta rama tiene un cambio sustancial de producto ($n_files archivos / $n_lines líneas vs origin/dev)."
echo "  Preguntale al dueño si corrés el retro (skill gobernanza → 'Retro de iniciativa' · /gobernanza)."
echo "  Si dice que sí: analizá qué rindió y qué no (honestidad > actividad) y REPARTÍ cada aprendizaje:"
echo "    • método de un skill        → buzón docs/PROPUESTAS_SKILLS.md (proponer, no aplicar)"
echo "    • criterio / arquitectura   → MEMORIA.md + DECISIONES.md (paridad, con OK del dueño)"
echo "    • cómo-funciona-X (gotcha)  → docs/SISTEMA_*.md (con OK)"
echo "    • principio de trabajo      → CLAUDE.md (Filosofía de trabajo, con OK)"
echo "    • trabajo diferido          → GitHub Issue (vía pendientes)"
echo "  Si no hubo nada que aprender, decilo — no fabriques churn."
exit 0
