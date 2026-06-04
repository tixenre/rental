# Handoff — Pedidos · Back-Office de Rambla Rental (DS v1)

Pantalla de **gestión de pedidos (alquileres)** del back-office admin: lista con
split master/detail, editor de pedido, máquina de estados, cobranzas y
comunicaciones (WhatsApp / Email con adjuntos PDF). Diseño hi-fi sobre el
**Design System de Rambla v1**.

| Superficie | Ruta (repo) | Stack |
|---|---|---|
| **Pedidos · Back-Office** | `/admin/pedidos` (verificar nombre del entity: `alquileres`) | React 19 + TanStack Router/Query + Tailwind v4 + shadcn/Radix + lucide-react |

---

## Qué hay en este bundle

```
design_handoff_pedidos/                ← lo que quedó commiteado en el repo
├── README.md                          ← este archivo
├── proto/                             ← sources del prototipo = referencia de CONDUCTA (se LEE, no es producción)
│   ├── data.js        ← mock de pedidos + helpers (espeja el modelo de alquileres)
│   ├── icons.jsx      ← set de íconos (en prod: lucide-react import individual)
│   ├── ui.jsx         ← primitivas + máquina de estados (transiciones, blockReason, nextStep)
│   ├── list.jsx       ← ListView: split master/detail, tabs, smart-chips, cards mobile
│   ├── editor.jsx     ← EditorView: cliente / fechas / equipos / notas + rail
│   ├── comms.jsx      ← CommsModal: plantillas WhatsApp / Email + adjuntos PDF
│   ├── app.jsx        ← shell: sidebar, topbar, ruteo list⇄editor, PagoModal, toasts, tweaks
│   └── tweaks-panel.jsx ← panel de Tweaks (solo pantalla)
└── src/                               ← scaffolds TSX que espejan los paths reales del repo
    ├── routes/admin/pedidos.tsx       ← ruta TanStack Router (scaffold)
    └── components/admin/PedidosBackoffice.tsx ← componente principal (tipos + máquina de estados + TODOs)

# NO commiteados — eran import-time y viven en el bundle original de Claude Design:
#   Pedidos Back-Office.html   ← referencia visual interactiva (se rasterizaba al importar)
#   assets/ (proto.css · fonts vendoreadas · wordmark) ← render-deps del .html (~1 MB, fuentes licenciadas)
```

> **Importante:** los `proto/*.jsx` son **referencias de diseño hechas en JS** — muestran
> el look & feel y el comportamiento final, no son el código a copiar tal cual. El target
> real de producción es el repo `tixenre/rental` (React + Tailwind v4); `src/` son
> scaffolds de partida con los `TODO:` marcados. El `.html` interactivo (panel de **Tweaks**
> de densidad, panel de detalle, cobranza en filas, modo oscuro) era **import-time y NO está
> commiteado** — para verlo, rasterizá el bundle original con `render.mjs`
> (`--both`, y `--eval`/`--click` para llegar a editor / modales / dark).

## Fidelidad

**Hi-fi.** Colores, tipografía, spacing, composición e interacciones finales.
Reproducir con los tokens del DS (`src/styles.css` del repo). La **referencia canónica de
layout y comportamiento** es el render del prototipo (`proto/*`); el `.html` que lo
empaquetaba era import-time y no se commiteó.

---

## Vistas y comportamiento

### Shell (`PedidosBackoffice`)
Sidebar (drawer en mobile) + topbar + ruteo interno **lista ⇄ editor**. Topbar
cambia según vista: en lista muestra breadcrumb + campana (con punto ámbar si hay
solicitudes pendientes); en editor muestra ‹ volver, nombre del cliente,
`EstadoBadge`, "Guardado" y botones Mail / WhatsApp.

### ListView (`proto/list.jsx`)
- **Split master/detail** (desktop): lista de 340px + `PreviewPane`. Colapsable
  con el botón panel. En mobile: **cards** apiladas.
- **Tabs:** Todos · Cobranzas · Solicitudes (badge con conteo de solicitudes).
- **Smart-chips:** Retiran hoy (ámbar) · Devuelven hoy (rosa) · Presupuestos
  nuevos (azul) · Con saldo (verde) — con conteo cada uno.
- **Búsqueda** por cliente o número + **chips de estado** (Activos / Solicitados /
  Confirmados / Cerrados / Todos).
- **MasterRow:** nombre + `EstadoBadge` + nº + fechas (o "RETIRA HOY" / "DEVUELVE
  HOY") + total + tag de cobranza (pagado / seña / sin seña).
- **PreviewPane:** próximo paso sugerido (CTA ámbar), fechas, total + cobranza,
  lista de equipos, acciones (WhatsApp / Email / Registrar pago / Documentos).

### EditorView (`proto/editor.jsx`)
- **2 columnas:** trabajo (`ed-main`) + rail (`ed-rail`).
- **Banner de solicitud** del cliente (cambio de fechas/items) con diff
  `was → now` y acciones Aprobar / Contraproponer / Rechazar.
- **Secciones:** Cliente (editable) · Fechas (retiro/devolución + jornadas +
  validación de stock) · Equipos (buscador para agregar + filas con `StepperPill`)
  · Notas internas.
- **Rail:** `EstadoDropdown` (deshabilita transiciones inválidas y muestra el
  motivo) + `FlowStrip` (progreso) + **Desglose** (bruto/desc/neto/IVA/total) +
  **Cobranza** (barra + pagos + registrar pago) + **Documentos** + eliminar.
- **Mobile:** barra inferior sticky con total + acciones.

### PagoModal (`proto/app.jsx`)
Registrar seña / saldo con presets (Seña 50% / Saldo total / Otro) y barra de
progreso. Si el pago cubre el saldo y el pedido está **devuelto**, se **finaliza**.

### CommsModal (`proto/comms.jsx`)
Plantillas de mensaje **sugeridas según el estado** del pedido (presupuesto,
confirmación, retiro, devolución, pago, libre) para **WhatsApp** o **Email**.
En email permite **adjuntar PDFs**: Remito · Contrato · Packing · Presupuesto
(defaults por plantilla).

---

## Máquina de estados (espeja el backend)

`borrador → presupuesto → confirmado → retirado → devuelto → finalizado`
(+ `cancelado` desde cualquier estado activo).

| Origen | Transiciones válidas |
|---|---|
| `borrador` | presupuesto · cancelado |
| `presupuesto` | confirmado · cancelado |
| `confirmado` | retirado · cancelado |
| `retirado` | devuelto · cancelado |
| `devuelto` | finalizado |
| `finalizado` / `cancelado` | — (terminal) |

**Bloqueos (`blockReason`):** pasar a `confirmado/retirado/devuelto/finalizado`
exige **fechas** y **al menos un equipo**. La UI deshabilita la opción y muestra
el motivo ("faltan fechas" / "sin equipos"). El código vive en
`src/components/admin/PedidosBackoffice.tsx` (`transiciones`, `blockReason`,
`nextStep`) — **mantener sincronizado con `ESTADOS_VALIDOS` del backend.**

**EstadoBadge — paleta de status oficial** (única fuente de chips de estado):
Presupuesto `azul` · Confirmado `verde` · Retirado `amber` · Devuelto `rosa` ·
Cancelado `destructive` · Borrador/Finalizado en gris/verde apagado.

---

## Componentes del DS a reusar

| Componente | Uso aquí |
|---|---|
| `EstadoBadge` (`kit/`) | **Único** chip de estado — en rows, preview, editor, topbar |
| `StepperPill` (`rental/`) | **Único** stepper — cantidades de equipos en el editor |
| `PriceBlock` (`kit/`) | Precios en `font-mono` (totales, líneas de equipo) |
| `StatCard` / `EmptyState` (`kit/`) | Conteos y estados vacíos ("Sin pedidos.") |
| `SearchInput` / `FieldLabel` / `Input` (`kit/`) | Búsqueda + campos del editor |
| `Button` (`ui/`) | variants `primary` (ink→amber) · `amber` · `outline` · `ghost` |
| `TopBar` (`rental/`, variant admin) | Si el repo ya tiene topbar admin, reusar |

> **Reuse-first.** No reinventar `StepperPill` ni `EstadoBadge`. Iconos:
> `lucide-react` import individual. Precios con `formatARS()`, fechas con
> `format()` + locale `es`.

---

## Datos — hooks / endpoints a implementar

| Hook / mutation | Qué hace | Notas |
|---|---|---|
| `usePedidos(filtros)` | Lista de alquileres + flags derivadas | reemplaza `RAMBLA.orders` (mock) |
| `useUpdatePedido(id)` | PATCH estado / cliente / items / notas / descuento | valida contra backend |
| `useRegistrarPago(id)` | POST pago (seña / saldo) | auto-finaliza si cubre y está devuelto |
| `useResolverSolicitud(id)` | Aprobar / contraproponer / rechazar | aplica cambio de fechas/items |
| `useCatalogo()` | Catálogo para "agregar equipo" | mock = `RAMBLA.CATALOGO` |
| `useEnviarComms(id)` | WhatsApp link (`wa.me`) / email server-side + adjuntos | plantillas en `proto/comms.jsx` |

**Campos del pedido usados:** `id`, `numero_pedido`, `estado`, `cliente
{nombre,email,telefono,perfil,tipo}`, `fecha_desde`, `fecha_hasta`,
`descuento_pct`, `items[] {equipo_id,nombre,marca,precio_jornada,cantidad,kit,
componentes}`, `pagos[] {monto,concepto,fecha}`, `notas`, `solicitud
{tipo,mensaje,was,now}`, y flags `retiraHoy` / `devuelveHoy` /
`tiene_solicitud_pendiente`.

**Desglose de precios:** el prototipo lo recalcula (`breakdown()`), pero la
**fuente de verdad es `services.precios`** del backend. Al integrar, usar los
montos persistidos; `breakdown()` queda solo para preview optimista.

**TODO / verificar contra el repo:**
- Nombre real del entity/ruta: ¿`pedidos` o `alquileres`? Ajustar `src/routes/`.
- `componentes` de kit: en el repo puede venir como `contenido_incluido_json`
  (string JSON) → parsear antes de renderizar.
- Confirmar `perfil` de IVA (`responsable_inscripto`) y la regla 21% contra
  `services.precios`.
- Auto-avances (asignar `numero_pedido` al confirmar; finalizar al cobrar saldo)
  deben resolverse **server-side**, no solo en cliente.

---

## Design tokens (del DS de Rambla)

| Token | Uso |
|---|---|
| `--amber` / `--amber-soft` | Acento, CTA primario, smart-chip "retiran hoy", foco |
| `--ink` | Texto, sidebar activo, caja de cobranza |
| `--background` / `--surface` / `--surface-elevated` | Fondo bone · paneles · cards/inputs/modales |
| `--hairline` | Bordes y divisores |
| `--muted-foreground` | Texto secundario, eyebrows mono |
| `--azul` / `--verde` / `--rosa` / `--naranja` / `--destructive` | Paleta de status (EstadoBadge / chips) |

**Tipografía:** `TT Commons` (UI) · `JetBrains Mono` (precios/fechas/nº/contadores,
tabular-nums) · `Champ Black` **solo** el wordmark del sidebar. **Radii:** inputs/
chips `sm` · botones `md` · cards `lg`. **ARS:** `$ 24.500`. **Dark mode** soportado
(`.dark` en `<html>`; el amber permanece).

---

## Checklist de implementación

- [ ] Confirmar ruta real (`/admin/pedidos` vs `/admin/alquileres`) y entity.
- [ ] Reemplazar mock `RAMBLA.orders` por `usePedidos()` + flags del backend.
- [ ] Cablear `useUpdatePedido` / `useRegistrarPago` / `useResolverSolicitud`.
- [ ] Sustituir chips por `EstadoBadge`, steppers por `StepperPill`, precios por `PriceBlock`.
- [ ] Verificar la máquina de estados contra `ESTADOS_VALIDOS` del backend.
- [ ] Mover auto-avances (numerar al confirmar, finalizar al cobrar) a server-side.
- [ ] Conectar `CommsModal` a WhatsApp (`wa.me`) y email + generación/adjunto de PDFs.
- [ ] Parsear `contenido_incluido_json` para componentes de kit.
- [ ] Iconos → `lucide-react` import individual; quitar el set inline de `proto/icons.jsx`.
- [ ] Responsive: split en desktop, cards + barra sticky en mobile; touch ≥ 44px; `dvh`.
