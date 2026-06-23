---
name: cola
description: El go-to para ADMINISTRAR LA COLA — issues, feature-requests, backlog y brain-dumps del dueño — sin que se desfase ni se pierda el hilo. Es el loop liviano y frecuente que mantiene la cola espejando el código real. Úsalo cuando el dueño diga "ordená los issues", "cómo está la cola", "qué hay pendiente", "triageá", "cerrá lo que ya está hecho", "etiquetá los issues", "consolidá los trackers", "metelo a la cola", "anotá esto", o cuando le pases un brain-dump de ideas/pedidos. El corazón es la RECONCILIACIÓN analítica (cruzar issues abiertos contra commits/PRs shippeados para cazar "hecho-pero-abierto") + el TRIAGE con evidencia + el reporte de salud "¿cómo está la cola?". NO es para auditar/limpiar el código (eso es `mantenimiento`), ni para cazar fallas a fondo (`auditoria-profunda`), ni para pulir el front (`pulido-frontend`). Este skill SOLO administra la cola: reconcilia, triagea, etiqueta, deduplica y reporta — el dueño dirige, la sesión recomienda.
model: sonnet
last-reviewed: 2026-06-23
version: 1.0
---

# cola — administrar la cola sin que se desfase

Codifica **cómo** se mantiene la cola de trabajo (issues / feature-requests / backlog) sana y al día,
para que el dueño **no pierda el hilo** ni la cola se desfase del código. No es la lista de lo pendiente
—esa vive en GitHub Issues— sino el **método** para reconciliarla, triagearla y reportarla con rigor.

Materializa dos decisiones de la memoria: **la cola espeja el código** (MEMORIA *2026-06-08 — Issues*) y
**el protocolo de brain-dumps del dueño** (MEMORIA pref *2026-05-25*). La regla de oro de `mantenimiento`
vale doble acá: **cerrar es afirmar "esto está hecho"** → no se cierra sin evidencia.

## Dónde encaja (no dupliques: delegá)

| Skill | Pregunta que responde | Entrada → Salida |
|---|---|---|
| **`cola`** (este) | "¿cómo está la cola? ordenala / triagéala / metelo a la cola" | issues abiertos + commits/PRs → cola reconciliada (cerrada lo hecho, etiquetada, deduplicada) + reporte de salud |
| `mantenimiento` | "auditá/limpiá el repo sin romper" | el repo → código sano (muerto/seguridad/ramas/split). Su **Frente D apunta acá** (esta es la fuente única de la cola). |
| `auditoria-profunda` | "cazá fallas a fondo, abrí issues" | el flujo de reserva + UI → hallazgos → issues nuevos (que después triagea ESTE skill) |

Qué reusás de los otros (NO lo re-expliques acá):

- **Regla de oro + método seguro** (verificá antes de actuar, honestidad > actividad, el dueño dirige) →
  `mantenimiento`. Acá "actuar" es **cerrar / consolidar / etiquetar mal**.
- **Labels** → `docs/ISSUE_LABELS.md` es la fuente única de las 3 dimensiones obligatorias + cross-cutting.
- **Workflow / `Closes #N` / auto-cierre en `dev→main`** → MEMORIA *2026-06-08 — Issues* y *Workflow de cambios*.

> **Herramientas.** Acá **no hay `gh` CLI** → todo por `mcp__github__*` (`list_issues`, `list_commits`,
> `list_pull_requests`, `search_issues`, `issue_write`, `add_issue_comment`). Ojo: `list_issues` devuelve
> `{issues, totalCount, pageInfo}` (un **dict**, no una lista).

## El método: reconciliar → triagear → deduplicar → etiquetar → intake → reportar

### 1 · RECONCILIAR — la cola espeja el código (el corazón analítico)

Es el paso que mata el desfasaje. La cola se desactualiza porque **se hace trabajo y no se cierra el
issue**. Para cazarlo:

- Listar issues abiertos (`list_issues`, ojo al dict) y agrupar por tópico.
- Cruzar cada uno contra lo **shippeado**: `list_commits` / `list_pull_requests` (buscar `Closes #N`,
  el número del issue, o el tema en títulos/bodies) y `search_issues`. El objetivo es separar:
  - **hecho-pero-abierto** → candidato a cerrar (con evidencia, paso 2).
  - **parcial** → queda abierto, se anota qué falta.
  - **backlog real** → queda abierto (no se entierra aunque "suene viejo").
- Recordá el auto-cierre: un issue con `Closes #N` en el PR se cierra **solo al promover `dev → main`**
  (la branch default es `main`). Si shippeó a `dev` pero no a prod todavía, **no está cerrado** aún.

### 2 · TRIAGE con evidencia — cerrar es afirmar

Un issue se cierra **solo** con un PR/commit que lo resuelve, o con confirmación explícita del dueño.

- Cerrar = `issue_write` con `state: closed` + `state_reason` (`completed` / `not_planned`) **+ un
  comentario** (`add_issue_comment`) que linkee la evidencia (PR/commit/decisión). Sin comentario, el
  "por qué se cerró" se pierde.
- **Parciales = abiertos.** Si el issue describe trabajo que **no** se hizo del todo, queda abierto y se
  anota qué falta (caso testigo histórico: #476, promover lint a bloqueante — era pendiente real).
- **El dueño dirige, la sesión recomienda.** Proponé la lista de cierres con su razón; el dueño da la
  orden. Ante un número dudoso (typos: "476" podía ser "477"), **confirmá** antes de cerrar.

### 3 · DEDUPLICAR / consolidar trackers

Cuando N issues cubren la misma iniciativa (caso testigo: DS #612/#605/#479 → #612; specs
#526/#528/#535 → #526):

- **Rescatá primero los ítems únicos** de cada uno hacia el tracker que sobrevive.
- **Después** cerrá los redundantes apuntando al consolidador.
- Un **umbrella** se cierra cuando su pasada está completa; si quedan sub-tareas, sobrevive con el
  checklist actualizado. Una **iniciativa multi-sesión = UN issue de tracking** (MEMORIA *2026-05-25*),
  no uno por fase.

### 4 · ETIQUETAR — 3 dimensiones obligatorias + cross-cutting

Fuente única: [`docs/ISSUE_LABELS.md`](../../../docs/ISSUE_LABELS.md). Todo issue lleva las **3
dimensiones obligatorias**: tipo (`bug`/`feature`/`refactor`/`documentation`/`design`/`security`) +
`priority:*` + `complexity:*`. Cross-cutting (cero o más):

- **`mobile`** → sube un nivel la prioridad efectiva (la mayoría del tráfico entra del celu).
- **`someday`** → separa la feature grande **diferida** de la cola accionable (no es deuda sin cerrar:
  queda asentada pero fuera de "qué hago ahora").
- `launch-blocker`, `infrastructure`, `backend`, `admin`, `dx`, `performance` según aplique.

Mantenimiento de labels: si un issue cambia de scope, **re-etiquetar la complejidad**; un
`priority:critical + complexity:epic` es señal de alarma → descomponer en pedazos accionables.

### 5 · INTAKE de brain-dumps del dueño

Cuando el dueño tira un brain-dump, triagear **cada ítem en el acto** y devolver un mapa corto
(MEMORIA pref *2026-05-25 — Protocolo de brain-dumps*):

- **Principio durable** → propuesta a la memoria (con aprobación del dueño; la sesión no escribe memoria sola).
- **Trabajo** → GitHub Issue (con sus 3 labels).
- **Pregunta** → respuesta.
- **Idea cruda** → igual va a issue (con `someday` si es diferida).

**Nada se borra.** Lo hecho-y-mergeado en la misma sesión **no lleva issue** (el commit es el registro);
el issue es para trabajo **diferido / multi-sesión / brain-dump** (MEMORIA *2026-06-08 — Issues*).

### 6 · "¿CÓMO ESTÁ LA COLA?" — el reporte de salud (el loop frecuente)

El reporte invocable que mata el desfasaje. Corré la reconciliación (paso 1) en modo read-only y devolvé
un resumen corto:

```
Estado de la cola — <fecha>
─────────────────────────────
Abiertos:                N
Probablemente hechos:    X  (→ proponer cierre con evidencia)
Duplicados / trackers:   Y  (→ consolidar)
Viejos / sin movimiento: Z
Gaps de label:           W  (issues sin las 3 dimensiones)
someday (diferidos):     S
```

**Sin cerrar nada solo** — el reporte propone, el dueño aprueba. Es liviano y frecuente a propósito:
corrércelo seguido es lo que evita que la cola se vuelva a desfasar.

## Regla de oro (heredada de `mantenimiento`, vale doble acá)

**Verificá antes de actuar — y "actuar" es cerrar, consolidar o etiquetar.** Cerrar un issue lo entierra;
consolidar mal pierde un ítem único; etiquetar mal desvía el triage. Nada se cierra sin **evidencia**
(PR/commit) o sin la orden del dueño. La **corazonada miente** ("casi todos se pueden cerrar" → varios
eran backlog real). Ante la duda: **se deja abierto y se reporta**. **Honestidad > actividad:** si la
cola está sana, la respuesta correcta es decirlo, no fabricar cierres para mostrar movimiento.

## Anti-objetivos (cuándo NO es este skill)

- **Auditar/limpiar el código** (muerto / seguridad / ramas / split de god-modules) → `mantenimiento`.
- **Cazar fallas a fondo** en el flujo de reserva o la UI → `auditoria-profunda` (que **abre** los issues
  que después triagea este skill).
- **Pulir una pantalla del front** → `pulido-frontend`.
- **Escribir memoria** → solo con aprobación del dueño, en paridad `MEMORIA.md` + `DECISIONES.md`. Este
  skill **propone** llevar un principio a la memoria; no la edita.

## Cheatsheet

```
1. RECONCILIAR: list_issues (dict!) + agrupar por tópico → cruzar contra list_commits/
   list_pull_requests/search_issues → separar hecho-pero-abierto / parcial / backlog real
   (ojo: Closes #N se cierra recién en dev→main, no al pushear a dev)

2. TRIAGE con evidencia: cerrar SOLO con PR/commit (issue_write state:closed + state_reason
   + comentario que linkee la evidencia) · parciales = abiertos · el dueño confirma números dudosos

3. DEDUPLICAR: rescatar ítems únicos primero → cerrar redundantes apuntando al consolidador
   (iniciativa multi-sesión = UN tracker)

4. ETIQUETAR: 3 dimensiones obligatorias (tipo + priority + complexity) + cross-cutting
   (mobile sube prioridad · someday separa diferido) — fuente única docs/ISSUE_LABELS.md

5. INTAKE brain-dump: principio→memoria(propuesta) · trabajo→issue · pregunta→respuesta ·
   idea→issue · nada se borra · lo hecho-y-mergeado-en-la-sesión NO lleva issue

6. "¿CÓMO ESTÁ LA COLA?": reporte de salud (abiertos / probablemente-hechos / duplicados /
   viejos / gaps de label / someday) — propone, NO cierra solo. El loop liviano y frecuente.

Al cerrar cada uso: escribir {"last-run": "<ISO UTC>"} en .claude/cola-state.json
(el hook SessionStart lo lee → avisa si lleva > 7 días sin revisar).
```

## Auto-mejora (correr al cerrar cada uso)

Preguntate, crítico: ¿alguna regla me desorientó o quedó vieja porque el repo cambió? ¿pegué un
gotcha que merece ser "caso testigo"? ¿overlap con otro skill? ¿repetí a mano un paso que debería
estar codificado acá?

Si **SÍ** → anotá la propuesta en [`docs/PROPUESTAS_SKILLS.md`](../../../docs/PROPUESTAS_SKILLS.md)
(formato: `fecha · skill · qué cambiar · por qué`). Proponés, no aplicás — el dueño aprueba, igual
que la memoria; el supervisor puede validar.

Si **NO** → no fabriques churn. **Honestidad > actividad.**
