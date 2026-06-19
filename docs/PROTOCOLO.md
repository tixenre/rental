# Protocolo — pasada de calidad + mobile gate

> El **método seguro** de mantenimiento (auditar → fixear con red de tests → commits atómicos →
> PR → supervisor) vive en el skill [`mantenimiento`](../.claude/skills/mantenimiento/SKILL.md) (5 frentes:
> código muerto/DRY · seguridad+bugs · ramas · issues · modularización/split). Este doc agrega lo que
> el skill **referencia** pero no contiene — la **rúbrica de auditoría** (su fase de diagnóstico) y el
> **mobile gate**.

---

## Cuándo correr una pasada de calidad

- Después de una racha de features con poco testing.
- Antes de un milestone (deploy, demo, freeze).
- Cuando "siento" deuda pero no sé dónde — la auditoría la mapea.
- Como rutina: cada 2-4 semanas.

El flujo concreto (qué tocar primero, cómo verificar, cómo no romper ni enterrar nada) → skill
`mantenimiento`. Convención de commits/branches → [`MANIFIESTO.md`](../MANIFIESTO.md) §3. El trabajo
pendiente se trackea en **GitHub Issues** (no en archivos `.md` — los viejos `BUGS.md`/`MEJORAS.md`
están en `docs/archive/`).

---

## Auditoría de calidad — rúbrica + método (read-only)

Diagnóstico profundo y **repetible**: no toca código (los hallazgos se **ejecutan** vía el skill
`mantenimiento`). Le da rigor al barrido informal — el Frente A (muerto/DRY/optimizar) y el Frente B
(seguridad+bugs) del skill se apoyan en esta rúbrica.

### Rúbrica — ejes (puntuar 1-5 por módulo; **N/A** si no aplica)

**Núcleo — un 🔴 acá bloquea el merge:**

- **A · Seguridad** — authz/authn (**verificar que cada endpoint use el guard CANÓNICO
  `admin_guard.require_admin` / `require_cliente`, no un `require_admin` local más débil**),
  inyección SQL / f-strings, SSRF, secrets, validación en el borde.
- **B · Correctitud** — bugs latentes, races, integridad transaccional (_la transacción es del
  caller_; `FOR UPDATE`), edge cases, idempotencia.
- **C · Integridad de datos / dominio** — plata en **enteros ARS**, multi-moneda no se mezcla,
  _plata congelada / contacto en vivo_, soft-delete, **core de reservas sagrado: cero overlap
  reimplementado fuera de `backend/reservas/`**.

**Calidad:**

- **D · Performance** — N+1, índices, queries en loop, payloads, hot paths; mobile (LCP / lazy).
- **E · Simplicidad** — longitud de funciones (**>80 = 🟡, >150 = 🔴**), anidamiento, complejidad.
- **F · Modularidad / fuente única** — no copy-paste, motores únicos (reservas / precios /
  contabilidad / búsqueda), fronteras netas, drift de decisiones de la memoria.
- **G · Fit / YAGNI** — dead code, over-engineering, endpoints que el front no usa.
- **H · Mantenibilidad** — comentarios que explican el _por qué_ y **no mienten**, docstrings
  exactos, naming consistente.
- **I · Observabilidad** — logging útil (`exc_info`), no tragar excepciones.
- **J · Cobertura de tests** — gaps (esp. HTTP de routes, round-trip de `dataio`).

**Transversales:**

- **L · API / contrato** — status codes correctos, shapes de error consistentes, **no filtrar
  `{e}` / tracebacks en la respuesta**, idempotencia de mutaciones.
- **M · Resiliencia** — timeouts (httpx / SMTP), degradación ante fallo de R2 / email / Didit /
  Maps, no bloquear el event loop (handler sync pesado → threadpool).
- **N · Privacidad / PII** — no PII en logs, ownership estricto, retención (**staging = copia de
  prod con PII real**).
- **O · Higiene de deps** _(periódico, no por-PR)_ — `pip-audit` / `npm audit`, pinning (`==`),
  supply-chain.

### Método (read-only)

1. **Scope** — listar el backend por área; priorizar lo grande / crítico.
2. **Dispatch en paralelo** — varios agentes read-only (`general-purpose` / `Explore`), **uno por
   área**, con esta rúbrica. Áreas típicas: _motores de dominio · routes · services/infra/dataio ·
   paquetes split_.
3. **Salida por módulo** — scorecard `eje:nota` (1-5) + hallazgos
   `archivo:línea | eje | 🔴/🟡/🟢 | qué | propuesta`.
4. **Verificar antes de reportar** — **todo 🔴 (sobre todo seguridad) se confirma leyendo el
   código**: los agentes exageran o se quedan cortos. Verificar también lo que "parece bien".
5. **Consolidar** — ranking de deuda por área + veredicto (¿profesional? ¿qué reescribir vs dejar?).
6. **Handoff** — los hallazgos priorizados → **GitHub Issues** (labels, ver `docs/ISSUE_LABELS.md`)
   y se ejecutan vía `mantenimiento` (su red de tests + supervisor). Los 🔴 de **seguridad / plata /
   reservas** → PR propia + supervisor + **test de regresión** (nunca un parche de apuro adentro
   del barrido).

---

## Mobile pass + gate (obligatorio)

**Cuándo es gate de merge:** un PR que toque rutas cliente (`/`, `/equipo/*`, `/cliente/*`,
`/estudio`, `/preguntas-frecuentes`) o admin prioritario (`/admin/pedidos`, `/admin/dashboard`)
**no se mergea** sin validar mobile — la mayoría del tráfico de un rental viene del celular.

**Por qué es visual:** no alcanza con revisar clases `hidden sm:*` en el código; hay componentes
que se renderizan pero no "se ven" (ej. carruseles sin flechas). Validar en viewport real
**375×667 (iPhone SE)**, mínimo objetivo del proyecto.

**Checklist rápido** (el criterio completo + el status por ruta viven en
[`docs/MOBILE_AUDIT.md`](MOBILE_AUDIT.md); cómo construir mobile → [`docs/MOBILE.md`](MOBILE.md)):

| | Checkpoint |
|---|---|
| ☐ | Sin scroll horizontal |
| ☐ | Tap targets ≥ 44px (`h-11 w-11`) — Apple HIG, MEMORIA *2026-06-05* |
| ☐ | Inputs ≥ 16px (si no, iOS zoomea) |
| ☐ | Modales/drawers entran en `100dvh` |
| ☐ | Carrito siempre accesible (sticky bar o header) |
| ☐ | Imágenes con `loading="lazy"` |

El smoke automatizado corre en CI (`.github/workflows/mobile-smoke.yml`, Playwright a 375px); no
reemplaza la validación visual del gate.

---

## Después del merge

- [ ] Items pendientes priorizados → crear/actualizar **GitHub Issues** (el tracking activo vive ahí).
- [ ] Si un bug revela una **clase de error recurrente**, proponé registrarlo (con aprobación del
  dueño): la **regla** en una línea al digest [`docs/MEMORIA.md`](MEMORIA.md) + el desarrollo
  **What / Why / How** al log [`docs/DECISIONES.md`](DECISIONES.md), mismo `fecha — título`.
- [ ] Si un bug requirió arreglo en runtime (database, infra) además del código, dejar nota en el
  commit + la PR.
