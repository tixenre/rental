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
- **Contexto / arquitectura** → `MANIFIESTO.md` (§6 decisiones fundacionales). El manual técnico del
  sistema de specs / catálogo → `docs/SISTEMA_SPECS.md`. Se lee on-demand.

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
| [`cola`](.claude/skills/cola/SKILL.md) | "ordená/triageá los issues", "¿cómo está la cola?", "cerrá lo hecho", brain-dumps → administrar la cola sin que se desfase | `sonnet` |
| [`mantenimiento`](.claude/skills/mantenimiento/SKILL.md) | "auditá/limpiá el repo", "¿hay deuda/legacy?", "modularizá ese god-module" → salud del repo en 5 frentes (muerto/seguridad/ramas/issues→`cola`/split) | `opus` |
| [`auditoria-profunda`](.claude/skills/auditoria-profunda/SKILL.md) | "auditá a fondo", "buscá fallas/bugs", "probá si es seguro / con mucha demanda", "screenshots en varios tamaños" → cazar fallas repetible (solo encuentra y documenta) | `opus` |
| [`pulido-frontend`](.claude/skills/pulido-frontend/SKILL.md) | "esta pantalla está rara / pulí la UX-UI" → diagnosticar y mejorar una pantalla que **ya existe** (no implementar un diseño dado) | `opus` |
| [`importar-diseno`](.claude/skills/importar-diseno/SKILL.md) | "implementá este handoff/mockup", "que el front/PDF quede como el diseño" → implementar un diseño **dado** + mantener la librería del DS | `sonnet` |
| [`gear-compatibility`](.claude/skills/gear-compatibility/SKILL.md) | "generá compatibilidades entre equipos" → razonar sobre specs (vía API; propuestas encolan para aprobación humana) | `sonnet` |

@docs/MEMORIA.md
