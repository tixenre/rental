---
name: pulido-frontend
model: opus
last-reviewed: 2026-06-23
version: 1.0
description: El go-to para AUDITAR y MEJORAR una pantalla/flujo del front que YA EXISTE y funciona, pero "está raro", no se ve bien, o se puede pulir. Flujo completo de calidad de experiencia — diagnosticar (rúbrica front-end, ejes P-U de PROTOCOLO) → rutear por riesgo → mejorar DS-first en 4 lentes (UX · UI/estética · modularización · performance) → verificar (render-compare + mobile gate + a11y + perf) → trackear página-por-página. Úsalo cuando el dueño diga "pulí la UX/UI", "esta pantalla está rara / no me cierra", "optimizá el flujo de X", "que se vea perfecto / más lindo", "mejorá la experiencia de X", "está lento el front", "modularizá esta pantalla", "auditá la UI de X con criterios de UX", o cuando detectes fricción/inconsistencia visual mientras trabajás. NO es para implementar un diseño ya hecho (handoff/mockup → skill `importar-diseno`), ni para diseñar desde cero (eso es Claude Design), ni para salud del repo / código muerto / seguridad (skill `mantenimiento`). Este skill DIAGNOSTICA qué falla en la experiencia y lo PULE de a poco — el corazón NO es una lista de fixes, sino el MÉTODO: recorrer la pantalla en vivo con rúbrica → rutear por riesgo → reusar/extender la librería del DS (nunca one-offs) → verificar contra el render real, mobile y accesibilidad → no romper el core de reservas. Delega: implementación fiel y motor render-compare en `importar-diseno`; método seguro + tests + supervisor en `mantenimiento`.
---

# pulido-frontend — auditar y pulir el front, pantalla por pantalla

Codifica **cómo** se sube la calidad de experiencia de Rambla sin romper nada y sin
churn de bajo valor: no la lista de lo que ya se pulió, sino el **método** para que cada
pasada de UX/UI futura sea rigurosa, consistente con el design system y segura. Es la
contraparte de front-end del par `PROTOCOLO` (rúbrica) + `mantenimiento` (método) que
ya existe para el backend.

## Dónde encaja (no dupliques: delegá)

Tres skills de front-end, tres preguntas distintas. Elegí por el **disparador**, no por el tema:

| Skill | Pregunta que responde | Entrada → Salida |
|---|---|---|
| `importar-diseno` | "tengo un diseño, **implementalo** fiel" | handoff/mockup de Claude Design → front real + librería del DS al día |
| **`pulido-frontend`** (este) | "esta pantalla **anda pero no está buena** — encontrá qué falla y mejorala, sistemático" | ruta en vivo + el DS → hallazgos UX/UI/perf/a11y → fixes in-place chicos **o** brief a Claude Design para un rediseño grande |
| `mantenimiento` | "**auditá/limpiá el repo** sin romper" | el repo → código sano (muerto/seguridad/ramas/issues/split) |

Qué reusás de los otros (NO lo re-expliques acá):

- **Motor visual `render.mjs`** (rasterizar rutas/HTML, `--both`, `--click`/`--eval` para estados
  internos) → vive en `importar-diseno`. Lo corrés tal cual.
- **Librería del DS y reuse-first** (chequear si un primitivo ya existe antes de crearlo; extraer
  a `src/design-system/{ui,kit} + src/components/{rental,admin}` + tokens en `src/design-system/styles/`) → es propiedad de `importar-diseno`.
  Este skill **consume** esa disciplina; no inventa componentes sueltos.
- **Método seguro** (rutear por riesgo, red de tests, commits atómicos, supervisor, el dueño prueba
  en staging) → `mantenimiento`. La regla de oro **"verificá antes de actuar"** y **"honestidad >
  actividad"** valen igual acá.
- **Rúbrica** → `docs/PROTOCOLO.md`. El backend se diagnostica con los ejes A-O; el **front-end con
  los ejes P-U** (agregados ahí por este skill). El mobile gate de PROTOCOLO es obligatorio.
- **Rediseño grande desde cero** (no pulido incremental) → se escribe un **brief**
  (`docs/design-brief-<feature>.md`), lo toma **Claude Design**, y el handoff vuelve por
  `importar-diseno`. Este skill **decide** cuándo hace falta eso (ver paso 2).

## El flujo: diagnosticar → rutear → mejorar → verificar → trackear

### 1 · DIAGNOSTICAR (read-only) — recorrer la pantalla con la rúbrica

No se toca nada todavía. Se **ve** la pantalla viva y se mapea la deuda de experiencia con los
**ejes P-U** de [`docs/PROTOCOLO.md`](../../../docs/PROTOCOLO.md):

- **P · UX / flujo** — ¿se completa la tarea sin fricción? pasos de más, callejones, **una sola
  forma de hacer cada cosa** (no 3 controles para 1 acción), labels que **prometen lo que hacen**.
- **Q · Jerarquía visual** — un solo foco primario por pantalla, el dato clave anclado, lectura
  clara, aire. (Dos CTAs del mismo peso = el ojo no sabe dónde ir.)
- **R · Consistencia con el DS** — tokens (cero hex/escala genérica), componentes reusados (no
  one-offs), spacing/eyebrows/tipografía consistentes, estados canónicos (`EstadoBadge`/`EmptyState`/skeleton).
- **S · Accesibilidad** — contraste WCAG (¡amber sobre blanco es borderline!), tap targets ≥44px,
  inputs ≥16px, `:focus-visible`, `aria-label` en icon-buttons, focus-trap en modales, orden de foco.
- **T · Performance percibida** — LCP mobile, lazy de imágenes/rutas, skeleton que espeja el layout
  (cero CLS), memo **solo con lag medido**, payloads, nada de trabajo pesado en el render path.
- **U · Estética / acabado** — alineación, ritmo, densidad, micro-interacciones canónicas, copy (voz
  "vos", precios por `formatARS()`, empty states accionables), pulido de detalle.

**Cómo VER (no adivinar):**

- **Ruta pública** → `node .claude/skills/importar-diseno/render.mjs /la-ruta --both` (desktop+mobile).
- **Estados internos** (editor, modal, dark) → `--click "<sel>"` / `--eval "<js>"` (rutean por estado
  de React, no por URL).
- **Ruta autenticada (admin/portal) o que use datos/assets reales** → los fixtures no alcanzan: los bugs
  de theming/datos no se ven con mocks (caso testigo: el wordmark custom del admin se veía amber sobre los
  topbars de color, invisible con el SVG bundleado local). Dos caminos, ambos vía **`staging-login`**
  (`target:"cliente"|"admin"`; MEMORIA *2026-06-19*, secreto en env, **nunca** en el repo): (a) recorrer
  **staging** con browser real; (b) **montar el entorno local con datos reales** —backend local + **BD de
  staging clonada a Postgres local** (dump read-only) + staging-login— y correr el render-compare **en vivo
  localmente** (MEMORIA *2026-06-20 — Iteración local con datos reales*; setup en `docs/DEPLOY_RAILWAY.md`).
  **Nunca** apuntar el backend local a la base remota. Caso testigo: la auditoría de **Pedidos** (staging) y
  el pulido del **portal cliente** (clon local, impersonando un cliente).
- **Mobile es obligatorio** — viewport real 375×667 (no alcanza leer clases `hidden sm:*`).

**Salida** = hallazgos en formato `pantalla:zona | eje | 🔴/🟡/🟢 | qué | propuesta`. Igual que el
backend, **todo 🔴 se confirma leyendo el código** antes de reportarlo (un agente exagera o se queda
corto). Esto es lo que produjo el audit de Pedidos; es la entrada de los pasos siguientes.

### 2 · RUTEAR por riesgo (mismo criterio que `mantenimiento`)

El cuidado es proporcional al radio de explosión. Clasificá cada hallazgo:

| Tipo | Qué es | Camino |
|---|---|---|
| **Pulido in-place chico** | label, color/token mal, spacing, aria, copy, lazy de una imagen | fix directo → `dev` (commit atómico) |
| **Refactor de componente** | extraer un one-off a la librería, unificar un patrón duplicado | reuse-first vía `importar-diseno`; red de tests; puede ir a `dev` si no cambia conducta |
| **Rediseño de pantalla/flujo** | la pantalla necesita repensarse (no parchar) | **brief → Claude Design → `importar-diseno`**; rama + PR; por fases si es grande (v2 al lado de v1) |
| **Toca lo que ve el cliente / core de reservas / plata** | rutas cliente, estados de pedido, disponibilidad | **rama + PR + supervisor + aviso**; el motor de reservas es sagrado, el pulido es **presentación**, no toca el cálculo |

Regla de ruteo (de la MEMORIA *2026-06-08 — Workflow de cambios*): trivial/normal → `dev` directo;
grande / sensible / core de reservas / lo que ve el cliente → rama (`claude/<desc>`) + PR. **Nunca a
`main` directo. No mergear con CI en rojo.**

> **La máquina de estados de la UI se DERIVA, no se inventa** (heredado de `importar-diseno`). El
> "siguiente paso" / qué transición ofrecer sale de (a) lo que la pantalla ya hace y (b) las
> precondiciones que valida el backend (`ESTADOS_VALIDOS` + checks en `routes/alquileres.py`). El flujo
> feliz lo guía la UI; el backend es la red que rechaza lo inválido. No hardcodees un grafo nuevo.

### 3 · MEJORAR — DS-first, en 4 lentes

Reuse-first **siempre**: antes de escribir, mirá si el primitivo ya existe (`Button`, `EstadoBadge`,
`PriceBlock`, `StatCard`, `EmptyState`, `StepperPill`, `Input`/`SearchInput`/`FieldLabel`…). Si existe
→ reusalo. Si el pulido necesita una pieza nueva reutilizable → **extraela a la librería**, no la
inlinees. Si un patrón está copiado en lista + editor → extraé **un** componente compartido (evita
drift). Las 4 lentes:

- **UX** — un solo modelo mental por acción; labels que ejecutan lo que dicen; menos pasos; empty/loading/
  error states accionables; el "siguiente paso" único y derivado del estado real.
- **UI / estética** — todo color de un token (tier 1-2; tiers 3-4 solo en constantes centralizadas;
  el guardrail de ESLint `no-restricted-syntax` bloquea escala genérica/hex); un `Section`/`RailSection`
  con padding consistente; eyebrows y tipografía por recipe; jerarquía con aire; micro-interacciones
  canónicas (press scale, hover lift, `--ease-*`).
- **Modularización** — partir god-components, extraer subcomponentes con frontera neta, mover lógica
  sensible a un hook único (caso `usePedidoDraft`: un solo camino de escritura para lista y editor).
  Move-verbatim cuando sea estructura pura; cambio de conducta = red de tests + aviso.
- **Performance** — `loading="lazy"` en imágenes, lazy de rutas pesadas, skeleton que espeja layout
  (cero CLS), `useMemo`/`memo` **solo si hay lag medido** (memo sin problema medido = deuda, no
  calidad), payloads chicos, nada bloqueante en el render. LCP mobile es el norte.

Todo cambio respeta `docs/DESIGN_SYSTEM.md` (tokens, componentes, voz/tono, mobile rules, "patterns
que nunca se rompen") — es la fuente canónica.

### 4 · VERIFICAR — render-compare + mobile + a11y + perf

Nada se da por bueno sin verlo:

- **Render-compare** — rasterizá la **ruta real** (desktop + mobile) y compará contra el antes / el
  mockup. Para rutas autenticadas, verificá con screenshots en staging (igual que `importar-diseno` paso 7).
- **Mobile gate (obligatorio, 375×667)** — el checklist de `PROTOCOLO`: sin scroll horizontal, tap
  targets ≥44px, inputs ≥16px, modales en `100dvh`, CTAs primarios en thumb-zone (mitad inferior),
  imágenes `lazy`. El smoke de CI (`mobile-smoke.yml`) corre solo, **no reemplaza** la validación visual.
- **Accesibilidad** — contraste de cada par texto/fondo (oscurecé o engrosá el amber sobre blanco si no
  pasa AA), `:focus-visible`, `aria-label` en icon-buttons, foco atrapado y autofocus en la acción
  primaria de modales.
- **Perf budget** — sin CLS al hidratar, sin regresión de LCP, lazy donde corresponde.
- **Suite + gates de CI** — `npx prettier --check` (bloqueante), `npx tsc --noEmit`, `npx eslint <archivos>`
  (no `eslint .` completo — cuelga en macOS; por archivos o esperá CI), `npm run build`, `npm run check:routes`
  (si tocaste ruteo: una lista con sub-rutas va como `.index`, ver gotcha de `importar-diseno`).

### 5 · TRACKEAR + cerrar

- **Página-por-página, no sprint.** El tablero de migración al DS vive en
  [#612](https://github.com/tixenre/rental/issues/612) (pantalla × estado). Cada pasada de pulido
  marca su fila en la misma PR — así "sabemos dónde estamos" y elegimos la próxima por prioridad.
- Hallazgos no atendidos → **GitHub Issues** con labels (`docs/ISSUE_LABELS.md`). Los 🔴 de a11y o de
  algo que ve el cliente → PR propia.
- **Commits atómicos** (Conventional Commits en español: `feat(admin):`, `fix(front):`, `refactor(scope):`),
  body con "lo que se dejó a propósito".
- **Supervisor** antes de abrir/mergear PR (instrucción de `CLAUDE.md`).
- **Plan de prueba en lenguaje claro** para el dueño ("andá a /X, hacé Y, tenés que ver Z") — el dueño
  prueba en **staging**, no lee diffs.

## Regla de oro (heredada, vale igual acá)

**Verificá antes de actuar — y "mejorar" puede empeorar.** Un rediseño puede romper un flujo que
funcionaba, un "lo hago más lindo" puede bajar el contraste o sacar un affordance. Ante la duda, se
**deja, se propone como issue, y se reporta** — no se reescribe a ciegas. **Honestidad > actividad:**
si una pantalla ya está bien, la respuesta correcta es decirlo, no fabricar churn. El gate del dueño
es *probar en staging*; "no romper la experiencia" pesa más que "cuánto la pulimos".

## Anti-objetivos (cuándo NO es este skill)

- **Implementar un diseño ya entregado** (carpeta `design_handoff_*/`, mockup pegado con "que quede
  así") → `importar-diseno`.
- **Diseñar una pantalla desde cero** → Claude Design (otro proyecto), entra por brief.
- **Código muerto / seguridad / ramas / issues / split de god-modules de backend** → `mantenimiento`.
- **Tocar el cálculo de reservas/plata** → sagrado; el pulido es presentación. Un bug del motor se
  reporta y va con plan + Opus + test, nunca dentro de una pasada de pulido.

## Cheatsheet

```
0. DIAGNOSTICAR (read-only): recorrer la pantalla VIVA (render.mjs --both / staging-login)
   con la rúbrica front-end (PROTOCOLO ejes P-U) + mobile 375
   → hallazgos pantalla:zona | eje | 🔴/🟡/🟢 | qué | propuesta   (confirmar cada 🔴 en el código)

1. RUTEAR por riesgo:
   pulido chico → dev directo · refactor de componente → reuse-first + tests
   rediseño de pantalla → brief → Claude Design → importar-diseno (rama+PR, por fases)
   cliente / core de reservas / plata → rama+PR + supervisor + aviso (el motor es sagrado)

2. MEJORAR DS-first, 4 lentes: UX (flujo/labels/un solo modelo) · UI/estética (tokens/aire/
   componentes) · modularización (extraer a la librería, hook único) · performance (lazy/memo
   medido/cero CLS/LCP). Reuse-first vía importar-diseno.

3. VERIFICAR: render-compare (desktop+mobile) · mobile gate 375 · a11y (contraste/targets/
   aria/foco) · perf budget · prettier+tsc+eslint+build (+ check:routes si tocaste ruteo)

4. TRACKEAR: marcar fila en #612 (misma PR) · issues con labels · commits atómicos →
   supervisor → plan de prueba → el dueño prueba en staging
```
