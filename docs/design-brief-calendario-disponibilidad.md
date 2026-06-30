# Design brief — Calendario de disponibilidad por equipo (#808)

> **Para Claude Design.** Esto es el _qué + contexto + objetivo_ (no el "cómo se ve" — eso lo
> resolvés vos). El backend ya está listo (endpoint abajo). Devolvé un handoff slim según
> `INSTRUCCIONES_CLAUDE_DESIGN.md` (referencia visual `.html` + `src/<path>.tsx` base + README con
> mapa elemento→token). Flujo: este brief → tu handoff → lo implementa Claude Code con `importar-diseno`.

## Qué / objetivo

Un **calendario de disponibilidad por equipo** en la **ficha técnica** del equipo
(`/equipo/$slug`, componente `EquipmentDetailBody` en `src/routes/equipo.$slug.tsx`). Que un
visitante del catálogo vea **de un vistazo** qué días ese equipo está libre, parcialmente
disponible o totalmente reservado, antes de elegir fechas. **Mobile-first** (la mayoría del
tráfico es celular). Es **informativo** (no se reserva desde el calendario en esta versión).

## Los 3 estados (esto es producto, no decisión visual — respetalos)

Cada día es uno de tres estados:

- 🟢 **libre** — todas las unidades del equipo están libres todo el día.
- 🟠 **parcial** — quedan algunas unidades pero no todas (ej. de 6 hay 3 libres), **o** el equipo
  se libera/ocupa a mitad del día (ej. lo devuelven 10am → libre a la tarde).
- 🔴 **reservado** — no hay ninguna unidad libre en todo el día.

Cómo se ven estos 3 estados (color, relleno, punto, celda partida para el parcial, etc.), la
leyenda, dónde se ubica el calendario en la ficha, la navegación de meses y los estados
loading/empty: **eso es lo que tenés que diseñar vos.** Mobile-first.

## Data contract (ya existe en el backend)

```
GET /api/equipos/{id}/disponibilidad-calendario?desde=YYYY-MM-DD&hasta=YYYY-MM-DD
→ 200 { "stock": 6, "dias": { "2026-09-05": "reservado", "2026-09-06": "parcial" } }
```

- Público (sin auth), catálogo-facing. `desde`/`hasta` opcionales (default hoy → hoy+90 días; cap 180).
- **`dias` solo trae los días NO libres** (`parcial`/`reservado`). Cualquier día del rango que **no**
  aparece es **libre** (🟢). `stock` = unidades totales (útil para un tooltip "quedan N").
- Es una **lectura** del motor de reservas (refleja ocupación física real). No hace falta endpoint nuevo.

## Reuse-first (recordatorio — la librería vive en el repo, no en el bundle)

- **Ya existe un calendario:** `src/design-system/ui/calendar.tsx` (wrapper de `react-day-picker`, soporta
  `modifiers` + classNames). Lo usa el date-picker del carrito (`DateRangePickerModal`). **Reusalo** —
  no diseñes un calendario desde cero; pensá los 3 estados como `modifiers` sobre ese componente.
- **Solo tokens del DS** (nada de hex; el guardrail de ESLint rompe el CI). Los 3 estados van a
  **colores semánticos** del sistema (mirá `src/design-system/styles/tokens/*` y `docs/DESIGN_SYSTEM.md`).
- Voz **"vos"**; fechas tipo `lun 2 jun.`; targets táctiles ≥ 44px; `font-mono` para números/fechas.

## Dónde va

Una **sección nueva** dentro de `EquipmentDetailBody` (la ficha del equipo ya carga el `equipo` con su
`id`). Es un **patch** sobre esa ruta existente (no una ruta nueva).

## Fuera de alcance (NO diseñar ahora)

- El calendario en la **vista grid y lista** del catálogo. Es una pregunta de diseño aparte que el dueño
  quiere resolver después — este brief es **solo la ficha del equipo**.
- Reservar/seleccionar fechas desde el calendario (esta versión es solo informativa).
