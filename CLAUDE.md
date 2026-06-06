# Rambla Rental — guía de sesión

> **Front door auto-cargado.** Liviano a propósito: el modus operandi esencial está acá; el
> contexto profundo se lee on-demand. **No** se inlinea el `MANIFIESTO.md` completo (~290 líneas)
> para no inundar la sesión — se lee cuando hace falta, y el supervisor lo lee en su ventana.

## Qué es

Plataforma de alquiler de equipos audiovisuales: catálogo público (`/`), portal cliente
(`/cliente/*`) y back-office admin (`/admin/*`). React 19 + Vite + TanStack / FastAPI +
PostgreSQL / deploy en Railway. Contexto completo → [`MANIFIESTO.md`](MANIFIESTO.md).

## Cómo trabajamos (esencial)

- **Branch + PR para lo grande; bugfixes chicos van directo a `dev`.** Lo grande / sensible /
  arquitectónico / que toca reservas o lo que ve el usuario = una rama (`claude/<desc>`) = una PR.
  Los **bugfixes chicos se commitean directo a `dev`** (se ven juntos en staging; un solo PR
  `dev → main` cuando el lote está listo) — ver `docs/MEMORIA.md` _2026-06-03_. Commits atómicos
  (Conventional Commits en español: `feat(scope):`, `fix(scope):`, `refactor`, `chore`, `docs`, ...).
  **Nunca commitear directo a `main`.**
- **La conversación es para decisiones y la forma de hacer las cosas — no para el ruido de cada
  commit/diff.** El trabajo de revisión pesada va al subagente `supervisor` (contexto aislado).
- **Antes de abrir/mergear una PR: despachar el agente `supervisor`** — revisión read-only de
  scope / forma / drift, que resume en lenguaje claro y deja el plan de prueba. (Instrucción, no
  gate de sistema: en las apps de Mac/iPhone no hay hooks.)
- **La sesión mergea a `dev`; el dueño gatea staging + promoción.** Mergear a `dev` = mostrar en
  staging (no es prod) → lo hace la sesión: chico/mediano con supervisor OK + checks verdes se
  mergea solo (directo o con auto-merge de GitHub); grande / sensible / que toca reservas o lo que
  ve el usuario se **avisa antes** de meterlo a `dev`. El dueño no clickea merges ya verificados —
  sus gates son **probar en staging** y **aprobar la promoción `dev → main`** (la puerta a prod).
  Ver `docs/MEMORIA.md` _2026-06-03 — Quién clickea el merge_.
- **No proponer ni hacer merge con CI en rojo.**
- **El dueño testea, no revisa código.** Acompañar cada cambio testeable con un **plan de prueba
  en lenguaje claro** ("andá a /X, hacé Y, tenés que ver Z"). El dueño prueba en **staging**; la
  promoción `dev → main` es su gate a prod.

## Memoria — dónde vive qué

- **Decisiones de criterio + preferencias** → [`docs/MEMORIA.md`](docs/MEMORIA.md) (curado; lo
  hace cumplir el supervisor). Agregar entradas **SOLO con aprobación explícita del dueño**; el
  supervisor propone, no escribe.
- **Trabajo pendiente** → GitHub Issues (la cola). Iniciativa multi-sesión → 1 issue de tracking
  por iniciativa, auto-mantenido por la sesión.
- **Registro de cambios** → commit history.
- **Contexto / arquitectura** → `MANIFIESTO.md` (§6 decisiones fundacionales). El manual técnico del
  sistema de specs / catálogo → `docs/SISTEMA_SPECS.md`. Se lee on-demand.

## Punteros

| Doc                                                                          | Para qué                                                                                                                                                                                                    |
| ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`MANIFIESTO.md`](MANIFIESTO.md)                                             | Qué es, stack, glosario, mapa de código, decisiones de arquitectura                                                                                                                                         |
| [`docs/MEMORIA.md`](docs/MEMORIA.md)                                         | Decisiones + preferencias vivas (importado abajo)                                                                                                                                                           |
| [`docs/FLUJO_PEDIDOS.md`](docs/FLUJO_PEDIDOS.md)                             | Recorrido del pedido: estados, confirmación visible, mails, `id` vs `numero_pedido`                                                                                                                         |
| [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md)                                     | Playbook de auditoría + PRs + mobile gate                                                                                                                                                                   |
| [`docs/ISSUE_LABELS.md`](docs/ISSUE_LABELS.md)                               | Labels (3 dimensiones obligatorias)                                                                                                                                                                         |
| [`docs/MOBILE_AUDIT.md`](docs/MOBILE_AUDIT.md)                               | Criterio mobile + status por ruta                                                                                                                                                                           |
| [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md)                             | Design system canónico: tokens, componentes, mobile rules, voz/tono, patterns                                                                                                                               |
| [`.claude/skills/importar-diseno/`](.claude/skills/importar-diseno/SKILL.md) | **Único skill de UI / front-end / design system / Claude Design / import + implementación.** Implementa handoffs en el front real (loop render-compare) Y mantiene/consume la librería del DS, que vive en la app: tokens en `src/styles/`, piezas en `src/components/`. Contrato del handoff: `INSTRUCCIONES_CLAUDE_DESIGN.md` |
| [`.claude/skills/limpieza/`](.claude/skills/limpieza/SKILL.md)               | Barrido de housekeeping seguro: código muerto / imports / archivos / deps / DRY, con el método y la red de tests (incl. Postgres real) para no romper nada                                                   |
| [`.claude/agents/supervisor.md`](.claude/agents/supervisor.md)               | El agente revisor                                                                                                                                                                                           |

@docs/MEMORIA.md
