# Protocolo — auditar bugs y mergear cambios prolijamente

> Este es el flujo que usamos en la sesión del **2026-05-10** para auditar el repo, fixear los críticos, y dejar todo trackeado.
> Servir como playbook para repetirlo cada vez que querramos hacer una pasada de calidad.

---

## Cuándo correr este protocolo

- Después de una racha de features con poco testing.
- Antes de un milestone importante (deploy, demo, freeze).
- Cuando "siento" que hay deuda pero no sé dónde — la auditoría la mapea.
- Cada 2-4 semanas como rutina de higiene.

---

## Fase 1 — Auditar (15-30 min)

**Objetivo**: encontrar bugs, NO arreglar. Reportar de forma estructurada.

### 1.1 Lanzar el agente auditor

```
Sos un auditor de código. Stack: <stack del proyecto>.
Working directory: el del repo (working dir de la sesión).

Contexto: <2-3 líneas sobre features recientes / cambios grandes>.

Buscá:
1. Bugs reales (rompen producción, pierden datos, vulnerabilidades).
2. Bugs latentes (edge cases sin cubrir, race conditions, asumir respuestas que pueden fallar).
3. Problemas de seguridad (endpoints sin auth, SSRF, secrets expuestos).
4. Problemas de UX que parecen bugs (toasts no montados, validación silenciosa).
5. Código muerto o duplicado.

Áreas a revisar (orden):
- <archivos que cambiaron mucho recientemente>
- <archivos críticos>

Reportá en formato:
## CRÍTICO (rompe producción / pierde datos / vulnerabilidad)
- [archivo:linea] Descripción 1-2 líneas. Fix sugerido (1 línea).
## ALTO (afecta UX, no rompe)
## MEDIO (latente, edge case)
## BAJO (cosmética, deuda técnica)

Importante:
- Sé concreto y técnico (no "podría haber problemas con X").
- Si no encontrás bugs en una categoría, escribí "ninguno".
- Calidad sobre cantidad. Densidad < 600 palabras.
```

Spawn como Explore agent (read-only) para que no toque nada.

### 1.2 Volcar los hallazgos a `BUGS.md`

Estructura:

```md
# Bugs — roadmap de fixes

> Auditoría hecha el YYYY-MM-DD. `[ ]` por hacer, `[x]` arreglado.

## CRÍTICO
- [ ] **<Título corto>** — `archivo:linea`. <Descripción del bug y su impacto>. **Fix**: <1 línea>.

## ALTO
## MEDIO
## BAJO

## Sugerencia de orden de ataque
1. Críticos restantes (típicamente fixes chicos).
2. Altos de UX (afectan el día a día).
3. Limpieza (pycache, código muerto).
4. Resto cuando se pueda.
```

### 1.3 (Opcional) `MEJORAS.md` con ideas

Si el agente o vos detectan ideas de features (no bugs), separarlas en otro archivo agrupadas por impacto/esfuerzo: Quick Wins, Medio, Grandes, Polish, Técnico/DX.

---

## Fase 1.5 — Mobile pass (10-15 min)

**Cuándo corre**: después de la auditoría general (Fase 1) y antes de fixear (Fase 2). También corre como **gate obligatorio** en cualquier PR que toque rutas de cliente o `/admin/pedidos|dashboard`.

**Objetivo**: verificar que lo que se renderiza en mobile se ve y funciona bien. El audit es visual — no alcanza con revisar clases `hidden sm:*` en el código; hay componentes que se renderizan pero no "se ven" (ej. carruseles sin flechas ni indicación de scroll).

### Viewports estándar

- **iPhone SE**: 375×667
- **iPhone 14 Pro**: 393×852

Usar Chrome DevTools → toggle device toolbar (Cmd+Shift+M) y elegir el viewport.

### Checklist rápido

| | Checkpoint |
|---|---|
| ☐ | Sin scroll horizontal (el ancho del viewport no se excede) |
| ☐ | Tap targets ≥ 44px (botones, links, CTA principales) — Apple HIG; `h-11 w-11` |
| ☐ | Inputs ≥ 16px para no disparar zoom en iOS |
| ☐ | Imágenes con `loading="lazy"` |
| ☐ | Modales y drawers caben en `100dvh` |
| ☐ | Carrito siempre accesible (sticky bar o header) |

Ver detalle completo en `docs/MOBILE_AUDIT.md`.

### Gate de merge

Si el PR toca alguna de estas rutas, el mobile pass es **obligatorio antes de mergear**:

- Rutas cliente: `/`, `/equipo/*`, `/cliente/*`, `/estudio`, `/preguntas-frecuentes`
- Admin prioritario: `/admin/pedidos`, `/admin/dashboard`

Para ver el backlog de issues mobile pendientes:

```bash
gh issue list --state open --label "mobile"
```

### Superficie mobile

No todo se renderiza en mobile. Antes de auditar, revisar `docs/MOBILE_AUDIT.md` sección "Superficie mobile" para saber qué esperar en viewport chico. Componentes marcados ❌ (no renderiza) están fuera del scope mobile.

---

## Fase 2 — Fixear con verificación (30-90 min)

**Una tanda = 4-6 fixes relacionados, NUNCA 20 cambios sueltos en un commit.**

### 2.1 Antes de cada fix

- Leer el archivo completo donde está el bug (no solo la línea).
- Buscar referencias a la función/key/variable involucrada (`grep -n`) por si el "fix" rompe otros lugares.
- Si el fix toca un endpoint con dependencias externas (Firecrawl, R2, OAuth), verificar **antes** que esas dependencias estén funcionando localmente.

### 2.2 Hacer el fix

- Cambio mínimo. Si querés refactorizar de paso, parar y separar en otro commit.
- Si el fix involucra reemplazo masivo (sed) sobre código vivo, **verificar caso por caso** que no toque strings con caracteres similares pero distinto significado (ej. `?` en regex vs SQL, `%s` literal vs placeholder).
- El sandbox puede bloquear sed masivos peligrosos — escuchar la alerta, no buscar atajo.

### 2.3 Tachar el bug en `BUGS.md`

Cambiar `[ ]` a `[x]` y agregar una nota tipo **FIX aplicado**: con explicación en 1-2 líneas.

### 2.4 Verificar

Antes de seguir con el próximo bug:

```bash
# TypeScript
node node_modules/.bin/tsc --noEmit

# Python (parsing)
cd backend && source .venv/bin/activate && python3 -c "
import ast, pathlib
for p in pathlib.Path('.').rglob('*.py'):
    if '.venv' in str(p) or '__pycache__' in str(p): continue
    ast.parse(p.read_text())
print('ok')
"

# Endpoints HTTP del flow afectado
curl -s -X POST http://localhost:8000/api/<endpoint> -H "Content-Type: application/json" -d '{...}'
```

Si el fix toca SQL, **al menos** un curl que ejecute esa query.
Si el fix toca un componente React, **abrir el browser** y hacer la acción (typecheck no detecta runtime errors).

---

## Fase 3 — Commits atómicos (10-15 min)

**Convención de commits** (estilo `tipo(scope):`, tipos válidos, body explica el *por qué*):
fuente única en [`MANIFIESTO.md`](../MANIFIESTO.md) §3 "Commits". No se repite acá.

**Lo propio de la auditoría**: **un commit = una unidad lógica** — una tanda son 4-6 fixes
relacionados, NUNCA 20 cambios sueltos en un commit.

### Plantilla

```
git commit -m "$(cat <<'EOF'
fix(backend): <título corto, imperativo, lowercase>

<por qué existía el bug, cómo se manifestaba, qué efectos tenía>

<si aplica: bullets con detalles>

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
EOF
)"
```

### Verificar antes de pushear

```bash
git status        # working tree limpio?
git log --oneline -<N>   # los commits cuentan la historia clara?
git ls-files | grep -E "(__pycache__|\.pyc$|\.env|secret)" # sin junk?
```

---

## Fase 4 — Push con PR (5 min)

**Nunca push directo a main desde una sesión de auditoría/fixes** — los cambios merecen revisión visible en GitHub.

### 4.1 Branch con nombre descriptivo

Convención de branches → fuente única en [`MANIFIESTO.md`](../MANIFIESTO.md) §3 "Branches"
(`claude/<descripcion>`, una rama por iniciativa). Para una pasada de auditoría:

```bash
git checkout -b claude/audit-and-fixes-YYYY-MM-DD
git push -u origin claude/audit-and-fixes-YYYY-MM-DD
```

### 4.2 Crear el PR (con `gh` o web)

Si tenés `gh` CLI:

```bash
gh pr create --base main --title "..." --body "$(cat <<'EOF'
## Resumen
<2-3 oraciones>

## Bugs criticos arreglados
| # | Bug | Archivo |
|---|---|---|

## Verificaciones pasadas
- [x] tsc --noEmit
- [x] curl endpoints afectados
- [x] sin .env ni secretos en el diff

## Test plan
- [ ] <cosa específica que el reviewer debería probar>

## Notas
<decisiones tomadas y por qué — ej. por qué NO se hizo cierto refactor>
EOF
)"
```

Sin `gh`, ir a la URL que GitHub devuelve después del push y pegar el body.

### 4.3 Instalar `gh` si no está

```bash
brew install gh
gh auth login
```

(esto debería hacerse una vez al setear el ambiente, no por sesión).

---

## Fase 5 — Después del merge

- [ ] Items pendientes priorizados → crear/actualizar GitHub Issues (el tracking activo vive ahí).
- [ ] Si hubo un bug que indica una clase de error recurrente (ej. "secuencias desincronizadas"), registrarlo en [`docs/MEMORIA.md`](MEMORIA.md) como preferencia/decisión (formato **What / Why / How to apply**) para no volver a caer.
- [ ] Si un bug requirió arreglo en runtime (database, infra) además del código, dejar nota en commit message + PR description.
- [ ] Borrar la branch local: `git branch -d chore/audit-and-fixes-YYYY-MM-DD`.

---

## Anti-patterns a evitar

| Tentación | Por qué evitarla | Qué hacer |
|---|---|---|
| "Lo pongo todo en un commit gigante" | Imposible de revertir, no se entiende qué arregló qué | Atomicidad: 1 commit = 1 idea |
| "Push directo a main" | Sin trazabilidad, sin revisión visible | Branch + PR siempre |
| `git push --force` | Reescribe historia compartida | Nunca a main; en branch propia OK con `--force-with-lease` |
| `git commit --no-verify` | Saltea hooks que protegen el repo | Investigar por qué falla el hook |
| sed `s/foo/bar/g` masivo | Toca strings que NO debías tocar (regex, URLs) | Caso por caso o script Python con AST |
| "El typecheck pasa, listo" | No detecta errores runtime ni UX rota | curl + browser + `BUGS.md` actualizado |
| Tachar bugs en `BUGS.md` sin verificar | Falsa sensación de progreso | Verificar el endpoint/UI antes de tachar |

---

## Comandos útiles cheatsheet

```bash
# Auditoría rápida de archivos sensibles
git ls-files | grep -E "(__pycache__|\.pyc$|\.env|secret|credential)"

# Ver qué cambió desde la última merge a main
git log origin/main..HEAD --oneline

# Verificar que un fix de secuencia Postgres se hizo bien
psql -c "SELECT setval('<tabla>_id_seq', (SELECT MAX(id) FROM <tabla>))"

# Buscar usos de una key/función antes de renombrar
grep -rn "nombreVariable" src/ backend/

# Ver el diff de un commit específico
git show <hash> --stat   # archivos
git show <hash>          # diff completo
```
