# Rambla Rental — guía de sesión

> **Front door auto-cargado.** Liviano a propósito: el modus operandi esencial está acá; el
> contexto profundo se lee on-demand. **No** se inlinea el `MANIFIESTO.md` completo (~290 líneas)
> para no inundar la sesión — se lee cuando hace falta, y el supervisor lo lee en su ventana.

## Qué es

Plataforma de alquiler de equipos audiovisuales: catálogo público (`/`), portal cliente
(`/cliente/*`) y back-office admin (`/admin/*`). React 19 + Vite + TanStack / FastAPI +
PostgreSQL / deploy en Railway. Contexto completo → [`MANIFIESTO.md`](MANIFIESTO.md).

## Cómo trabajamos (esencial)

- **El workflow de cambios tiene _fuente única_:** la decisión _2026-06-08 — Workflow de cambios_ del
  digest (auto-cargada abajo). En una línea: **routing por riesgo** (trivial/normal → push directo a
  `dev` = staging; grande / sensible / core de reservas o plata / lo que ve el cliente → rama
  (`claude/<desc>`) + PR), **la sesión mergea a `dev` y avisa con plan de prueba**, los **gates del
  dueño** son probar en staging + aprobar `dev → main`. **Nunca a `main` directo; no mergear con CI en
  rojo.** El detalle y el _por qué_ no se repiten acá — viven en esa decisión.
- **Antes de abrir/mergear una PR: despachar el agente `supervisor`** — revisión read-only de
  scope / forma / drift, que resume en lenguaje claro y deja el plan de prueba. (Instrucción, no
  gate de sistema: en las apps de Mac/iPhone no hay hooks.)
- **La conversación es para decisiones y la forma de hacer las cosas — no para el ruido de cada
  commit/diff.** El trabajo de revisión pesada va al subagente `supervisor` (contexto aislado).
- **El dueño testea, no revisa código.** Acompañar cada cambio testeable con un **plan de prueba
  en lenguaje claro** ("andá a /X, hacé Y, tenés que ver Z"). El dueño prueba en **staging**.

## Memoria — dónde vive qué

- **Decisiones de criterio + preferencias** → [`docs/MEMORIA.md`](docs/MEMORIA.md) — el **digest
  enforceable** (regla de cada decisión en 1-3 líneas, auto-cargado abajo); el **_por qué_ completo**
  vive en el log on-demand [`docs/DECISIONES.md`](docs/DECISIONES.md) (mismo `fecha — título`). Lo
  hace cumplir el supervisor. Escribir/editar/podar **SOLO con aprobación explícita del dueño** (toca
  ambos archivos en paridad); el supervisor propone, no escribe.
- **Trabajo pendiente** → GitHub Issues (la cola). Iniciativa multi-sesión → 1 issue de tracking
  por iniciativa, auto-mantenido por la sesión.
- **Registro de cambios** → commit history.
- **Contexto / arquitectura** → `MANIFIESTO.md` (§6 decisiones fundacionales). Los **manuales técnicos por
  sistema** (fuente única del "cómo funciona X", índice en MANIFIESTO §8) → `docs/SISTEMA_SPECS.md`
  (specs/catálogo), `docs/SISTEMA_FOTOS.md` (fotos/media). Se leen on-demand.

## Punteros

| Doc                                                                          | Para qué                                                                                                                                                                                                    |
| ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`MANIFIESTO.md`](MANIFIESTO.md)                                             | Qué es, stack, glosario, mapa de código, decisiones de arquitectura                                                                                                                                         |
| [`docs/MEMORIA.md`](docs/MEMORIA.md)                                         | **Digest enforceable** de decisiones + preferencias vivas, 1-3 líneas c/u (importado abajo)                                                                                                                 |
| [`docs/DECISIONES.md`](docs/DECISIONES.md)                                   | Log ADR completo (el _por qué_ de cada decisión), on-demand — mismo `fecha — título` que el digest                                                                                                          |
| [`docs/FLUJO_PEDIDOS.md`](docs/FLUJO_PEDIDOS.md)                             | Recorrido del pedido: estados, confirmación visible, mails, `id` vs `numero_pedido`                                                                                                                         |
| [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md)                                     | **Rúbrica de auditoría** (ejes A-O + scorecard + método) + **mobile gate** (el método de mantenimiento → skill `mantenimiento`)                                                                                    |
| [`docs/ISSUE_LABELS.md`](docs/ISSUE_LABELS.md)                               | Labels (3 dimensiones obligatorias)                                                                                                                                                                         |
| [`docs/MOBILE_AUDIT.md`](docs/MOBILE_AUDIT.md)                               | Criterio mobile + status por ruta                                                                                                                                                                           |
| [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md)                             | Design system canónico: tokens, componentes, mobile rules, voz/tono, patterns                                                                                                                               |
| [`.claude/agents/supervisor.md`](.claude/agents/supervisor.md)               | El agente revisor                                                                                                                                                                                           |

## Skills — cuál uso para qué (+ modelo)

> **Mapa de fronteras canónico.** Elegí el skill por el **disparador**, no por el tema. La columna
> **Modelo** materializa _2026-05-26 — Eficiencia de sesión_ (criterio/diagnóstico → Opus; ejecución
> mecánica → Sonnet) en el frontmatter `model:` de cada skill: al invocarlo, **cambia el modelo solo**.
> Los skills de criterio (Opus) **delegan la ejecución mecánica a subagentes `model: sonnet`**.
> `scripts/check-docs.mjs` verifica que todo skill en disco esté listado acá y bien formado.

| Skill | Cuándo lo uso (disparador) | Modelo |
| --- | --- | --- |
| [`pendientes`](.claude/skills/pendientes/SKILL.md) | "ordená/triageá los issues", "¿cómo están los pendientes / la cola?", "cerrá lo hecho", brain-dumps → administrar la cola de pendientes sin que se desfase | `sonnet` |
| [`mantenimiento`](.claude/skills/mantenimiento/SKILL.md) | "auditá/limpiá el repo", "¿hay deuda/legacy?", "modularizá ese god-module" → salud del repo en 5 frentes (muerto/seguridad/ramas/issues→`pendientes`/split) | `opus` |
| [`auditoria-profunda`](.claude/skills/auditoria-profunda/SKILL.md) | "auditá a fondo", "buscá fallas/bugs", "probá si es seguro / con mucha demanda", "screenshots en varios tamaños" → cazar fallas repetible (solo encuentra y documenta) | `opus` |
| [`pulido-frontend`](.claude/skills/pulido-frontend/SKILL.md) | "esta pantalla está rara / pulí la UX-UI" → diagnosticar y mejorar una pantalla que **ya existe** | `opus` |
| [`design-system`](.claude/skills/design-system/SKILL.md) | "auditá el DS", "el DS está drifting", "cómo está el DS", "buscá reimplementaciones/colores hardcodeados/violaciones a los 11 principios", "mantenimiento del DS" → gobernador del DS: auditoría sistémica + dashboard `/ds` + propone issues; `pulido-frontend` aplica | `opus` |
| [`gear-compatibility`](.claude/skills/gear-compatibility/SKILL.md) | "generá compatibilidades entre equipos" → razonar sobre specs (vía API; propuestas encolan para aprobación humana) | `sonnet` |
| [`gobernanza`](.claude/skills/gobernanza/SKILL.md) | "¿cómo están los skills?", "qué skills tenemos", "revisá la gobernanza", "hay skills solapados?", "propuestas pendientes", "cierre mensual" → auditar y curar la capa de skills (dashboard `/skills`, auditoría, buzón, ledger, consolidación dry-run) | `opus` |
| [`calidad-codigo`](.claude/skills/calidad-codigo/SKILL.md) | "el código está bien escrito?", "hay anti-patrones?", "qué tan escalable está el repo?", "auditá la calidad del código", "hay duplicación lógica?", "los patterns de React están bien usados?" → evalúa TypeScript, patterns React, duplicación lógica, naming, complejidad; propone issues | `opus` |
| [`auditoria-seguridad`](.claude/skills/auditoria-seguridad/SKILL.md) | "auditá la seguridad", "hay vulnerabilidades?", "está seguro el auth?", "revisá CORS/headers", "qué tan vulnerable está?", "OWASP", "revisá las dependencias" → auditoría sistemática: auth, CORS, headers HTTP, inputs, secretos, deps | `opus` |
| [`performance`](.claude/skills/performance/SKILL.md) | "está lenta la app?", "el bundle es muy pesado?", "hay N+1?", "Core Web Vitals", "qué tan rápido carga?", "auditá la performance", "hay queries lentas?" → bundle, code splitting, re-renders, N+1, caching | `opus` |
| [`specs`](.claude/skills/specs/SKILL.md) | "auditá las specs", "las specs están inconsistentes?", "qué specs faltan?", "hay specs duplicadas con nombres distintos?", "el sistema de specs está sano?", "normalizá las specs" → gobernador de la taxonomía de specs de equipos | `opus` |
| [`catalogo`](.claude/skills/catalogo/SKILL.md) | "los equipos están completos?", "qué equipos les faltan fotos?", "hay equipos sin descripción?", "auditá el catálogo", "qué está incompleto?", "los equipos están bien cargados?" → completitud del catálogo: fotos, descripciones, specs, precios | `opus` |
| [`calidad-tests`](.claude/skills/calidad-tests/SKILL.md) | "cómo están los tests?", "hay paths sin tests?", "qué falta testear?", "auditá la cobertura", "los tests son buenos?", "qué casos borde no están testeados?" → cobertura de módulos críticos, calidad de assertions, edge cases sin tests | `opus` |
| [`marca`](.claude/skills/marca/SKILL.md) | "actualizá el marketing", "qué features no están comunicadas?", "el marketing está al día?", "auditá la marca", "qué hay de nuevo desde la última campaña?", "qué features tiene la web?" → gobernador de marca: cruza features reales vs. docs/MARCA.md + CAMPAÑA_FEATURES.md, propone updates y borradores de copy | `opus` |

@docs/MEMORIA.md
