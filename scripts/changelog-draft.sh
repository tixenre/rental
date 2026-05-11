#!/usr/bin/env bash
# changelog-draft.sh — genera borradores de entradas para src/data/changelog.ts
# a partir de los PRs mergeados que todavía no están registrados.
#
# Uso:
#   ./scripts/changelog-draft.sh             # imprime drafts de los PRs faltantes
#   ./scripts/changelog-draft.sh --limit 50  # más PRs (default: 30)
#
# El output es TypeScript pegable directo al inicio del array changelog en
# src/data/changelog.ts. Después editás los body/title con lenguaje claro
# antes de commitear — el script solo da el esqueleto.

set -euo pipefail

LIMIT="${LIMIT:-30}"
if [[ "${1:-}" == "--limit" && -n "${2:-}" ]]; then
  LIMIT="$2"
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHANGELOG="$ROOT/src/data/changelog.ts"

if [[ ! -f "$CHANGELOG" ]]; then
  echo "❌ No encontré $CHANGELOG" >&2
  exit 1
fi

# Números de PR ya registrados en el changelog (number: <N>)
REGISTERED=$(grep -oE "number:\s*[0-9]+" "$CHANGELOG" | grep -oE "[0-9]+" | sort -un)

# PRs mergeados de GitHub
PRS_JSON=$(gh pr list --state merged --limit "$LIMIT" --json number,title,mergedAt,labels)

# Filtrar los que NO están en el changelog
MISSING=$(echo "$PRS_JSON" | jq -r --argjson registered "$(echo "$REGISTERED" | jq -R . | jq -s .)" '
  map(select(.number | tostring as $n | $registered | index($n) | not))
')

count=$(echo "$MISSING" | jq 'length')

if [[ "$count" -eq 0 ]]; then
  echo "✅ Changelog al día — todos los PRs recientes ya están registrados."
  exit 0
fi

echo "// ─────────────────────────────────────────────────────────────────"
echo "// $count PRs faltantes en changelog.ts (revisar y curar los textos)"
echo "// ─────────────────────────────────────────────────────────────────"
echo ""

echo "$MISSING" | jq -r '
  .[] |
  (.title | capture("^(?<t>feat|fix|chore|docs|style|refactor|perf|test)") // {t: "chore"}) as $kind |
  (.title | sub("^(feat|fix|chore|docs|style|refactor|perf|test)(\\([^)]+\\))?:\\s*"; "")) as $clean |
  (.mergedAt | split("T")[0]) as $date |
  ([.labels[].name] | map(select(. != "bug" and (startswith("priority:") | not) and . != "launch-blocker" and . != "feature"))) as $extraLabels |
  ($kind.t | if . == "perf" then "fix" elif . == "test" then "chore" else . end) as $tsType |
  ($extraLabels | map("\"" + . + "\"") | join(", ")) as $labelsStr |
  "  {\n    number: \(.number),\n    date: \"\($date)\",\n    type: \"\($tsType)\",\n    title: \"\($clean)\",\n    body: \"TODO: redactar en lenguaje claro para el usuario.\",\n    labels: [\($labelsStr)],\n  },\n"
'

echo ""
echo "// Para pegar al inicio del array \`changelog\` en src/data/changelog.ts."
echo "// Editar 'title' y 'body' antes de commitear — el script solo da el draft."
