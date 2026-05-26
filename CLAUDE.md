# Rambla Rental — guía de sesión

> **Front door auto-cargado.** Liviano a propósito: el modus operandi esencial está acá; el
> contexto profundo se lee on-demand. **No** se inlinea el `MANIFIESTO.md` completo (~290 líneas)
> para no inundar la sesión — se lee cuando hace falta, y el supervisor lo lee en su ventana.

## Qué es

Plataforma de alquiler de equipos audiovisuales: catálogo público (`/`), portal cliente
(`/cliente/*`) y back-office admin (`/admin/*`). React 19 + Vite + TanStack / FastAPI +
PostgreSQL / deploy en Railway. Contexto completo → [`MANIFIESTO.md`](MANIFIESTO.md).

## Cómo trabajamos (esencial)

- **Branch + PR siempre.** Una iniciativa = una rama (`claude/<desc>`) = una PR con commits
  atómicos (Conventional Commits en español: `feat(scope):`, `fix(scope):`, `refactor`, `chore`,
  `docs`, ...). No commitear directo a `main`.
- **La conversación es para decisiones y la forma de hacer las cosas — no para el ruido de cada
  commit/diff.** El trabajo de revisión pesada va al subagente `supervisor` (contexto aislado).
- **Antes de abrir/mergear una PR: despachar el agente `supervisor`** — revisión read-only de
  scope / forma / drift, que resume en lenguaje claro y deja el plan de prueba. (Instrucción, no
  gate de sistema: en las apps de Mac/iPhone no hay hooks.)
- **Merge según tamaño:** trivial/small con CI verde + supervisor OK → auto-merge; sensible /
  arquitectónico / grande, o que toca lo que ve el usuario → **PR draft + el dueño prueba** primero.
- **No proponer merge con CI en rojo.**
- **El dueño testea, no revisa código.** Acompañar cada cambio testeable con un **plan de prueba
  en lenguaje claro** ("andá a /X, hacé Y, tenés que ver Z"). Pre-lanzamiento: el dueño prueba en
  prod (decisión con disparador en `docs/MEMORIA.md`).

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

| Doc | Para qué |
|---|---|
| [`MANIFIESTO.md`](MANIFIESTO.md) | Qué es, stack, glosario, mapa de código, decisiones de arquitectura |
| [`docs/MEMORIA.md`](docs/MEMORIA.md) | Decisiones + preferencias vivas (importado abajo) |
| [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md) | Playbook de auditoría + PRs + mobile gate |
| [`docs/ISSUE_LABELS.md`](docs/ISSUE_LABELS.md) | Labels (3 dimensiones obligatorias) |
| [`docs/MOBILE_AUDIT.md`](docs/MOBILE_AUDIT.md) | Criterio mobile + status por ruta |
| [`.claude/agents/supervisor.md`](.claude/agents/supervisor.md) | El agente revisor |

@docs/MEMORIA.md
