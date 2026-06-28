#!/bin/bash
# Stop hook — revisión de gobernanza auto-ruteada (Nivel 1 de "que los evals se usen solos").
#
# Si la rama actual tocó la capa de skills o el digest de memoria, recordá —UNA vez por cambio-set,
# NO en cada turno— correr la señal del harness de evals (scripts/evals/README.md) que corresponde.
# La parte mecánica (context-size) la corre solo; la inteligente (supervisor / routing-judge) la
# surfacea como recordatorio dirigido: un shell no puede despachar un agente.
#
# Corre en la TERMINAL (CLI), NO en las apps de Mac/iPhone (ahí no hay hooks) — ese es el punto.
# Falla SIEMPRE en silencio (exit 0): un hook nunca debe interrumpir la sesión.

root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$root" 2>/dev/null || exit 0

# Paths cambiados: lo que la rama agregó vs origin/dev + lo no-commiteado (staged y working).
changed="$( {
  base="$(git merge-base HEAD origin/dev 2>/dev/null || true)"
  [ -n "$base" ] && git diff --name-only "$base" HEAD 2>/dev/null
  git diff --name-only 2>/dev/null
  git diff --name-only --cached 2>/dev/null
} | sort -u )"

skills_hit="$(printf '%s\n' "$changed" | grep -E '^\.claude/skills/' | grep -v '/\.archive/' || true)"
digest_hit="$(printf '%s\n' "$changed" | grep -E '^docs/(MEMORIA|DECISIONES)\.md$' || true)"

[ -z "$skills_hit" ] && [ -z "$digest_hit" ] && exit 0

# Dedupe por cambio-set: solo recuerda una vez por combinación de paths tocados (estado gitignored).
state="$root/.claude/.governance-review-state"
sig="$(printf '%s|%s' "$skills_hit" "$digest_hit" | cksum 2>/dev/null | cut -d' ' -f1)"
[ -n "$sig" ] && [ "$(cat "$state" 2>/dev/null)" = "$sig" ] && exit 0
[ -n "$sig" ] && printf '%s' "$sig" > "$state" 2>/dev/null || true

echo "⚠ Gobernanza — esta rama tiene cambios sin validar con el harness (scripts/evals/README.md):"
if [ -n "$digest_hit" ]; then
  echo "  • Tocaste el digest (docs/MEMORIA|DECISIONES) → corré la SEÑAL B (catch del supervisor vs fixtures/*.diff) antes del PR."
  node scripts/evals/context-size.mjs 2>/dev/null | tail -4 || true
fi
[ -n "$skills_hit" ] && echo "  • Tocaste la capa de skills → corré la SEÑAL C (routing-judge vs routing-cases.jsonl) + considerá /gobernanza."
exit 0
