---
name: gobernanza
description: El go-to para AUDITAR Y CURAR la capa de skills y docs de gobernanza — el meta-nivel del sistema de trabajo. Dashboard "/skills" (qué hay, último uso, staleness, propuestas), auditoría de drift/overlap/bloat/routing, consumo del buzón de propuestas y el ledger de uso, consolidación en modo dry-run (propone, archiva-no-borra), y cierre periódico mensual. Úsalo cuando el dueño pida "cómo están los skills", "qué skills tenemos", "revisá la gobernanza", "hay skills solapados?", "qué se usó", "propuestas pendientes", "cierre mensual de gobernanza", o cuando el sistema mismo proponga una revisión. El corazón es el ciclo LEER-PROPONER-APROBAR: el skill lee (ledger + buzón + check-docs), razona, propone cambios en lenguaje claro — el dueño aprueba, la sesión aplica. NO aplica cambios sin aprobación, NO toca código de la app, NO administra issues de GitHub (eso es `pendientes`), NO decide la memoria (la propone).
model: opus
last-reviewed: 2026-06-23
version: 1.0
---

# gobernanza — auditar y curar la capa de skills

Codifica **cómo** se mantiene el sistema de gobernanza (skills + docs) sano, vigente y sin drift,
para que el dueño **no pierda la noción de qué skills tiene ni de cómo el sistema evoluciona**. Es
el meta-nivel: los otros skills describen cómo hacer el trabajo del repo; éste describe cómo cuidar
a los skills mismos.

Blueprint: Curator de Hermes Agent — **nativo, no un segundo agente**. Modo **propone-aprobás**
(dry-run por default): el skill razona y propone, el dueño aprueba, la sesión aplica. Materializa la
decisión _Capa de skills auto-gobernada (MEMORIA 2026-06-23)_.

## Dónde encaja (no dupliques: delegá)

| Skill | Pregunta que responde | Entrada → Salida |
|---|---|---|
| **`gobernanza`** (este) | "¿cómo está el sistema de skills? ¿qué hay, qué se usa, qué driftea?" | ledger + buzón + skills en disco → propuestas de curación aprobables |
| `pendientes` | "¿cómo están los pendientes / la cola de issues?" | issues abiertos + commits → cola reconciliada |
| `mantenimiento` | "¿cómo está el código?" | el repo → código sano (5 frentes) |
| `auditoria-profunda` | "¿tiene fallas / bugs?" | flujo de reserva + UI → hallazgos |

**Fuentes de datos que consume este skill:**
- `.claude/skill-ledger.jsonl` — telemetría de uso (qué skills se invocan de verdad)
- `docs/PROPUESTAS_SKILLS.md` — buzón de mejoras propuestas durante el uso
- `scripts/check-docs.mjs` — brazo mecánico: verifica drift sin que haya que leer todo
- Los propios `SKILL.md` de cada skill (lectura profunda)
- `CLAUDE.md` — la tabla canónica (mapa de fronteras)

## El método: leer → auditar → proponer → aprobar → aplicar

### 1 · `/skills` — dashboard de estado (el comando liviano)

Responde "perdí la noción de qué skills tengo" sin hacer una auditoría completa. Corré cuando el
dueño pida un resumen rápido:

```
Estado de skills — <fecha>
──────────────────────────
Skills en disco: N  (listados en CLAUDE.md: M)
Último uso por skill (del ledger):
  cola           → <fecha> (hace X días)
  mantenimiento  → <fecha> (hace Y días)
  …              → sin registro
Staleness (> 120 días sin revisar): <lista o "ninguno">
Propuestas pendientes en buzón: P  (<resumen de títulos>)
```

Fuentes: `readdirSync(.claude/skills)` + `skill-ledger.jsonl` + `PROPUESTAS_SKILLS.md`. Es read-only.

### 2 · Auditoría de la capa (el trabajo profundo)

Corré `node scripts/check-docs.mjs` primero — caza los errores mecánicos (drift paridad, links rotos,
frontmatter mal formado, skill en disco sin fila en CLAUDE.md, falta Auto-mejora). Si falla, eso va
primero.

Después, lectura profunda de cada `SKILL.md`:

- **Drift de `model:`** — ¿el modelo asignado sigue teniendo sentido? (criterio/diagnóstico → opus;
  ejecución/loop frecuente → sonnet). ¿Coincide con la columna Modelo de la tabla en CLAUDE.md?
- **Overlap** — ¿dos skills cubren casos demasiado similares? ¿conviene fusionar o aclarar fronteras?
  (caso testigo: `auditoria-profunda` + `pulido-frontend` + `mantenimiento` — fronteras distintas pero
  se solapan en "auditar el front". Evaluar si el mapa de fronteras en CLAUDE.md es lo suficientemente
  claro.)
- **Staleness de contenido** — ¿el método del skill refleja cómo trabaja el repo HOY? (cambios de
  arquitectura, herramientas nuevas, paths que se movieron, decisiones que cambiaron el flujo)
- **Bloat** — ¿algún skill creció tanto que debería partirse?
- **Cross-refs rotas** — ¿los punteros internos del skill siguen siendo válidos? (rutas, secciones,
  archivos referenciados)
- **Auto-mejora** — ¿el buzón tiene propuestas para este skill? ¿son válidas hoy?

### 3 · Consumir el buzón (`docs/PROPUESTAS_SKILLS.md`)

Leer cada propuesta acumulada. Para cada una:
1. ¿Sigue siendo relevante? (el repo puede haber evolucionado)
2. ¿Es tratable en esta sesión o requiere más contexto?
3. ¿Hay conflicto con otra decisión de la memoria?

Proponer al dueño qué aprobar, qué descartar y qué diferir. **No aplicar sin aprobación.**

### 4 · Consumir el ledger (`.claude/skill-ledger.jsonl`)

Parsear el ledger para responder:
- Qué skills se usan de verdad (frecuencia, última vez)
- Qué skills nunca se invocan (candidatos a archivar o fusionar)
- Si el uso coincide con el `model:` declarado (ej: un skill sonnet que se usa 0 veces vs. uno opus
  que se llama a diario para tareas mecánicas → puede valer la pena bajar el modelo)

```bash
# Conteo por skill desde el ledger
python3 -c "
import json
from collections import Counter
from pathlib import Path
lf = Path('.claude/skill-ledger.jsonl')
if lf.exists():
    counts = Counter(json.loads(l)['skill'] for l in lf.read_text().splitlines() if l.strip())
    for s, n in counts.most_common(): print(f'{n:4}  {s}')
else:
    print('Ledger vacío o no existe.')
"
```

### 5 · Proponer consolidación (dry-run)

Si la auditoría detecta un skill redundante o sin uso:
- **Proponer** al dueño: "el skill X no se usa hace N meses y su método está cubierto por Y → propongo
  archivarlo".
- **Archivar, no borrar** → `git mv .claude/skills/<x>/ .claude/skills/.archive/<x>/` (queda en git,
  reversible). El linter ignora `.archive/` (los dirs con `.` al inicio).
- El dueño aprueba, la sesión ejecuta el `git mv`.

### 6 · Cierre de gobernanza periódico (mensual)

El ritual que convierte "tengo telemetría" en "el sistema aprende con el tiempo". Producir un digest:

```
Cierre de gobernanza — <mes YYYY>
──────────────────────────────────
Skills activos: N  |  Archivados: M  |  Nuevos: P
Uso en el mes (del ledger): <ranking por skill>
Staleness: <skills > 120 días sin revisar>
Buzón: <propuestas pendientes / aplicadas / descartadas>
Drift detectado por check-docs: <errores / warnings>
Decisión sugerida: <1-2 líneas de qué cambiar o "sin cambios">
```

El dueño revisa y aprueba. Lo que se aprueba: aplicar propuestas del buzón, archivar skills, ajustar
`model:`, actualizar `last-reviewed`. **Todo va a memoria + DECISIONES en paridad** si es una
decisión de criterio nueva.

## Regla de oro

**Proponer, no aplicar.** Este skill razona sobre el meta-nivel y lleva propuestas al dueño — igual
que el supervisor. Nunca edita un skill, la memoria ni CLAUDE.md sin aprobación explícita. La
honestidad vale más que el movimiento: si la capa está sana, la respuesta correcta es decirlo.

**Auditarse a sí mismo.** Al correr este skill, aplicar también los pasos 2-3 sobre `gobernanza/SKILL.md`
mismo: ¿el método sigue siendo válido? ¿el overlap con el supervisor está bien aclarado?

## Anti-objetivos (cuándo NO es este skill)

- **Administrar la cola de issues** → `pendientes`.
- **Auditar fallas de seguridad / UI del repo** → `auditoria-profunda` / `pulido-frontend`.
- **Hacer trabajo del repo** (código, frontend, backend) → cualquier otro skill.
- **Escribir memoria** → solo con aprobación del dueño, en paridad. Este skill propone; no edita.
- **Supervisar un PR** → agente `supervisor` (tiene su propia ventana de contexto aislada).

## Auto-mejora (correr al cerrar cada uso)

Preguntate, crítico: ¿alguna regla me desorientó o quedó vieja porque el repo cambió? ¿pegué un
gotcha que merece ser "caso testigo"? ¿overlap con otro skill (especialmente con el supervisor)?
¿repetí a mano un paso que debería estar codificado acá?

Si **SÍ** → anotá la propuesta en [`docs/PROPUESTAS_SKILLS.md`](../../../docs/PROPUESTAS_SKILLS.md)
(formato: `fecha · skill · qué cambiar · por qué`). Proponés, no aplicás — el dueño aprueba.

Si **NO** → no fabriques churn. **Honestidad > actividad.**

## Cheatsheet

```
/skills  →  dashboard rápido (ledger + buzón + staleness) — siempre read-only

Auditoría completa:
  1. node scripts/check-docs.mjs (mecánico: drift/links/frontmatter/Auto-mejora)
  2. Lectura profunda skills → drift model: / overlap / staleness / bloat / cross-refs
  3. Ledger: python3 -c "..." → ranking de uso real
  4. Buzón PROPUESTAS_SKILLS.md → filtrar relevantes → proponer al dueño

Consolidación (dry-run):
  → proponer archivar skills sin uso: git mv .claude/skills/X/ .claude/skills/.archive/X/
  → el dueño aprueba, la sesión ejecuta

Cierre mensual:
  → digest (uso / staleness / buzón / drift) → dueño revisa → aplica lo aprobado
  → si hay decisión nueva: memoria + DECISIONES en paridad
```
