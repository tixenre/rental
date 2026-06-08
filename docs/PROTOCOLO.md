# Protocolo — pasada de calidad + mobile gate

> El **método seguro** de mantenimiento (auditar → fixear con red de tests → commits atómicos →
> PR → supervisor) vive en el skill [`limpieza`](../.claude/skills/limpieza/SKILL.md) (4 frentes:
> código muerto/DRY · seguridad+bugs · ramas · issues). Este doc **no lo repite**: agrega lo propio
> de una pasada de calidad que el skill no cubre — el **prompt del auditor** y el **mobile gate**.

---

## Cuándo correr una pasada de calidad

- Después de una racha de features con poco testing.
- Antes de un milestone (deploy, demo, freeze).
- Cuando "siento" deuda pero no sé dónde — la auditoría la mapea.
- Como rutina: cada 2-4 semanas.

El flujo concreto (qué tocar primero, cómo verificar, cómo no romper ni enterrar nada) → skill
`limpieza`. Convención de commits/branches → [`MANIFIESTO.md`](../MANIFIESTO.md) §3. El trabajo
pendiente se trackea en **GitHub Issues** (no en archivos `.md` — los viejos `BUGS.md`/`MEJORAS.md`
están en `docs/archive/`).

---

## Prompt del auditor (read-only)

Lanzar como **Explore agent** (no toca nada). Complementa el frente B del skill `limpieza`:

```
Sos un auditor de código. Stack: React 19 + Vite + TanStack / FastAPI + PostgreSQL.
Working directory: el del repo.

Contexto: <2-3 líneas sobre features recientes / cambios grandes>.

Buscá:
1. Bugs reales (rompen producción, pierden datos, vulnerabilidades).
2. Bugs latentes (edge cases, race conditions, asumir respuestas que pueden fallar).
3. Seguridad (endpoints sin auth, SSRF, secrets expuestos).
4. UX que parece bug (toasts no montados, validación silenciosa).
5. Código muerto o duplicado.

Áreas (orden): <archivos que cambiaron mucho> → <archivos críticos>.

Reportá:
## CRÍTICO (rompe producción / pierde datos / vulnerabilidad)
- [archivo:linea] Descripción 1-2 líneas. Fix sugerido (1 línea).
## ALTO (afecta UX, no rompe)  ## MEDIO (latente)  ## BAJO (cosmética)

Sé concreto y técnico. Si no hay hallazgos en una categoría, "ninguno".
Calidad sobre cantidad. Densidad < 600 palabras.
```

Los hallazgos priorizados van a **GitHub Issues** con sus labels (ver `docs/ISSUE_LABELS.md`).

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
