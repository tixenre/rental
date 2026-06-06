# Teardown de Booqable — qué adoptar

> **Qué es esto.** El dueño usa Booqable hoy y lo va a dejar cuando Rambla Rental esté listo.
> Booqable tiene flujos que vale la pena "robar". Este doc los lista, **priorizados**, y los mapea
> contra lo que **Rambla ya tiene** — para no reimplementar lo hecho y enfocar el backlog en los
> huecos reales. Output del issue **#485**.
>
> **Cómo leer la tabla.** ✅ = ya está en Rambla (no hay nada que adoptar). ⚠️ = está a medias
> (hay un hueco concreto). ❌ = no existe (candidato a adoptar). El detalle de cada hueco está más
> abajo, con su issue candidato.
>
> ⚠️ **Caveat de honestidad:** este teardown está armado desde las features **conocidas** de
> Booqable + lo ya referenciado en #74 y #83 (la sesión no tiene acceso a la cuenta de Booqable del
> dueño). **El dueño es quien lo completa/corrige** con lo que ve día a día en la herramienta —
> sobre todo micro-flujos del operador (atajos, escaneo, etc.) que no se ven desde afuera. Marcá
> acá lo que falte y lo bajamos a issues.

---

## Mapa: Booqable vs Rambla

| Área de Booqable | Estado en Rambla | Dónde vive / qué falta |
| --- | --- | --- |
| Detalle de pedido (tabla productos, steppers, rail derecho) | ✅ (Pedidos v2, #748) | `src/components/admin/pedido/` — falta línea libre, dropdown de unidad, tags, drag-reorder (#74) |
| Workflow de estados del pedido (concept→reserved→started→stopped) | ✅ | `docs/FLUJO_PEDIDOS.md` + `backend/reservas/estados.py` |
| Documentos (cotización, contrato, remito, packing) | ✅ (#83 cerrado) | `backend/pdf_templates.py` — 5 docs alineados al mockup |
| Pagos (parciales, seña, saldo, registrar/borrar) | ✅ | `alquiler_pagos` + `RegistrarPagoModal.tsx` |
| Portal del cliente (self-service) | ✅ | `src/routes/cliente.portal.tsx` |
| Catálogo / ficha de equipo (público + admin) | ✅ | `src/routes/equipo.$slug.tsx` |
| Reportes / liquidación / comisiones | ✅ | `backend/reportes/` |
| Notas internas en el pedido | ✅ | `alquileres.notas` |
| Mails automáticos al cliente (creado/confirmado/recordatorio) | ⚠️ construido, **apagado** | `backend/services/email/` — falta activar por ops (env vars) |
| Calendario de disponibilidad (vista admin) | ⚠️ parcial | `CalendarioWidget.tsx` + feed iCal — falta matriz por-equipo |
| **Línea personalizada** (ítem de texto libre, fuera del catálogo) | ❌ | hueco de #74 — ver abajo |
| **Unidad de cargo por línea** (jornada / día / semana) | ❌ | hueco de #74 — ver abajo |
| **Etiquetas en el pedido** (chips/labels) | ❌ | hay tags en equipos, no en pedidos — ver abajo |
| **Depósito / seña de garantía** explícito | ❌ (¿confirmar?) | ver abajo |
| **Escaneo / check-out · check-in** del equipo (código de barras/QR) | ❌ | ver abajo |
| **Campos custom** en pedido/cliente/equipo | ❌ (parcial vía specs) | ver abajo |
| **Pago online** (cliente paga desde el portal, MP/Stripe) | ❌ | ver abajo |
| **WhatsApp** como canal de notificación | ❌ (skeleton listo) | follow-up de notificaciones canal-agnósticas |

---

## Prioridad 1 — huecos chicos de alto valor (cierran #74)

Estos tres son los que el propio #74 dejó abiertos tras Pedidos v2. Son lo más cercano a "terminar
de robarle a Booqable el detalle de pedido".

### 1.1 — Línea personalizada (ítem de texto libre)
- **Booqable:** podés agregar a un pedido una línea que **no** es del catálogo (ej. "Flete",
  "Operador 4h", "Limpieza") con nombre, cantidad y precio libres.
- **Rambla hoy:** toda línea es un `alquiler_item` ligado a un `equipo`. No hay ítem libre.
- **Por qué importa:** hoy el dueño no puede cobrar extras/servicios en el mismo pedido → los mete
  a mano por fuera o como un equipo trucho. Ensucia el inventario y la liquidación.
- **Cuidado (core sagrado):** una línea libre **no reserva stock** → no debe pasar por el gate de
  `backend/reservas/`. Modelarla como `alquiler_item` con `equipo_id NULL` + flag/`tipo`, excluida
  de la expansión de disponibilidad. Tocar plata (totales, IVA, liquidación) con cuidado.
- **Issue candidato:** sub-issue de #74.

### 1.2 — Unidad de cargo por línea (jornada / día / semana)
- **Booqable:** cada línea tiene un dropdown de período de cobro (por hora / día / semana / fijo).
- **Rambla hoy:** todo se cobra por jornada (con la lógica de `@/lib/pricing` / `services/precios.py`).
- **Por qué importa:** alquileres largos (semana/mes) o cobros fijos no encajan en "por jornada".
- **Cuidado:** es lógica de **plata** → vive en el motor de precios, no ad-hoc en el componente.
  Coordinar con cómo `priceBreakdown()` y `services/precios.py` calculan hoy.
- **Issue candidato:** sub-issue de #74.

### 1.3 — Etiquetas en el pedido + drag-reorder de líneas
- **Booqable:** chips/labels arbitrarios en el pedido ("urgente", "productora X", "retira en local")
  y reordenar líneas arrastrando.
- **Rambla hoy:** hay etiquetas en **equipos** (`equipo_etiquetas`), no en pedidos. El orden de
  líneas es fijo.
- **Por qué importa:** las etiquetas son el filtro/triage rápido del operador en el listado.
- **Issue candidato:** sub-issue de #74 (o issue propio si crece).

---

## Prioridad 2 — flujos del operador que Booqable hace bien

### 2.1 — Calendario de disponibilidad por-equipo (matriz/planning)
- **Booqable:** vista de planning tipo Gantt — filas = productos, columnas = días, se ve **qué está
  reservado cuándo** y se puede mover/editar desde ahí.
- **Rambla hoy:** `CalendarioWidget` (conteos agregados por día) + feed iCal + cards "salen/devuelven
  hoy". No hay matriz por-equipo ni edición desde el calendario.
- **Por qué importa:** es la forma natural de ver huecos y evitar choques de un vistazo. Hoy hay que
  entrar pedido por pedido.
- **Cuidado:** es **lectura** sobre el motor de reservas — debe leer de `backend/reservas/`
  (disponibilidad), no recalcular overlap por su cuenta. Empezar read-only (sin drag-edit).
- **Issue candidato:** nuevo, `feature` + `complexity:large`.

### 2.2 — Check-out / check-in del equipo (retiro y devolución asistidos)
- **Booqable:** al retirar/devolver marcás ítem por ítem (con escaneo de código de barras/QR
  opcional) qué salió y qué volvió, y detecta faltantes.
- **Rambla hoy:** el packing list (PDF con checkboxes) cubre la versión en papel; el estado
  `retirado`/`devuelto` es a nivel pedido, no ítem por ítem en pantalla.
- **Por qué importa:** menos errores de qué volvió y qué no; base para "equipo dañado/faltante".
- **Issue candidato:** nuevo, `feature` + `complexity:medium`. **Confirmar con el dueño** si lo usa
  en Booqable y cuánto.

### 2.3 — Activar los mails (no es feature, es ops)
- **Rambla hoy:** infra de mails 100% construida pero en modo `test` (no envía). Falta setear
  `RESEND_API_KEY`/`SMTP_*` + `EMAIL_FROM` + `EMAIL_ADMIN_TO` en prod.
- **Por qué importa:** Booqable manda confirmaciones/recordatorios solo; Rambla ya los tiene escritos,
  solo hay que prenderlos. Tarea de **ops**, no de código.
- **Issue candidato:** nuevo, `chore` — tarea de configuración.

---

## Prioridad 3 — adoptar si el negocio lo pide (no urgente)

### 3.1 — Depósito / seña de garantía explícita
- **Booqable:** monto de garantía que se retiene y se devuelve, separado del pago del alquiler.
- **Rambla hoy:** hay "seña" como pago parcial, pero no un **depósito reembolsable** modelado aparte.
- **Confirmar:** ¿el dueño cobra depósito de garantía hoy? Si no, no se adopta.

### 3.2 — Pago online desde el portal (MP / Stripe)
- **Booqable:** el cliente paga o deja la seña online al confirmar.
- **Rambla hoy:** los pagos se registran a mano en el admin; el cliente no paga online.
- **Por qué importa:** ya hay analytics y portal; sería el cierre del loop de reserva.
- **Issue candidato:** iniciativa propia (proveedor + integración + conciliación). `complexity:large`.

### 3.3 — Campos custom (pedido / cliente / equipo)
- **Booqable:** campos definibles por el usuario en pedidos/clientes/productos.
- **Rambla hoy:** los equipos tienen specs estructuradas (`equipo_specs`), pero no hay campos custom
  libres en pedidos/clientes.
- **Confirmar:** ¿qué campos usa el dueño en Booqable que hoy no tiene? Esa lista define el alcance.

### 3.4 — WhatsApp como canal de notificación
- **Rambla hoy:** las notificaciones son canal-agnósticas (decisión 2026-05-27); el skeleton está,
  WhatsApp es follow-up (requiere proveedor Meta/Twilio + plantillas aprobadas).
- **Issue candidato:** iniciativa propia cuando se encare.

---

## Cómo seguimos

1. **El dueño revisa esta tabla** y marca: qué de los ❌/⚠️ realmente usa en Booqable (sobre todo
   P2/P3, que dependen del negocio), y qué micro-flujos del operador faltan que no se ven desde afuera.
2. Con eso confirmado, se bajan a **GitHub Issues** los que correspondan (la P1 ya tiene casa en #74).
3. Cuando se migre de Booqable de verdad, este doc se relee como checklist final de paridad.
