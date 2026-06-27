#!/bin/bash
# pre-promote.sh — checklist + chequeos ANTES de promover dev → main (PROD).
#
# Corrélo en la raíz del repo cuando estés por shippear a producción. Te muestra QUÉ iría a prod,
# corre el chequeo mecánico de gobernanza (check-docs) solo, y te RECUERDA lo que un shell no puede
# hacer por vos: despachar el supervisor y probar el flujo en la app. Falla suave (no rompe nada).

cd "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || { echo "No es un repo git."; exit 1; }

echo "═══ Pre-promoción  dev → main (PROD) ═══"
echo

# 1) Scope: qué se promovería
git fetch -q origin main dev 2>/dev/null
range="origin/main..origin/dev"
git rev-parse --verify -q origin/main >/dev/null 2>&1 || range="main..dev"

n="$(git rev-list --count "$range" 2>/dev/null || echo '?')"
echo "📦 Iría a prod: $n commit(s)"
git log --oneline "$range" 2>/dev/null | head -20 | sed 's/^/   /'
echo
echo "   archivos tocados:"
git diff --stat "$range" 2>/dev/null | tail -12 | sed 's/^/   /'
echo

# 2) Chequeo mecánico (lo que el script SÍ puede correr)
echo "🔧 check-docs (paridad digest↔log + links):"
node scripts/check-docs.mjs 2>&1 | tail -1 | sed 's/^/   /'
echo

# 3) Checklist humano (lo que el script NO puede hacer por vos)
echo "✅ Confirmá a mano antes de promover:"
echo "   □ Despachaste el SUPERVISOR sobre el diff dev→main (scope · drift · forma)"
echo "   □ Probaste el flujo crítico EN LA APP local (reserva, etc.) — no solo que pasen los tests"
echo "   □ CI en verde en dev"
echo
echo "Las tres en ✓ → promové (PR dev→main). Alguna en duda → frená."
