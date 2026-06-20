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
| [`.claude/skills/importar-diseno/`](.claude/skills/importar-diseno/SKILL.md) | **Único skill de UI / front-end / design system / Claude Design / import + implementación.** Implementa handoffs en el front real (loop render-compare) Y mantiene/consume la librería del DS, que vive en la app: tokens en `src/styles/`, piezas en `src/components/`. Contrato del handoff: `INSTRUCCIONES_CLAUDE_DESIGN.md` |
| [`.claude/skills/mantenimiento/`](.claude/skills/mantenimiento/SKILL.md)               | **El go-to para auditar y mejorar el repo.** Diagnosticar (rúbrica de `PROTOCOLO`) → rutear por riesgo → ejecutar en **5 frentes** (A código muerto/DRY/optimizar · B seguridad+bugs · C ramas · D issues · **E modularización / split de god-modules, move-verbatim y gateado**), con el método y la red de tests (incl. Postgres real) para verificar antes de actuar y no romper ni enterrar nada |
| [`.claude/skills/gear-compatibility.md`](.claude/skills/gear-compatibility.md) | Genera relaciones de compatibilidad entre equipos (cámaras/lentes/luces/monitores/grabadores) razonando sobre specs; complementa el algoritmo determinístico `_compute_compat`. Siempre vía API del backend (nunca toca la DB directo); las propuestas de specs encolan para aprobación humana |
| [`.claude/agents/supervisor.md`](.claude/agents/supervisor.md)               | El agente revisor                                                                                                                                                                                           |

@docs/MEMORIA.md
