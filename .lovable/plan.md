
## Objetivo

Reemplazar el wizard modal y el `PedidoDetailSheet` por una **página única estilo Booqable** que sirva tanto para crear como para editar pedidos. Pensada para borradores rápidos: con apenas cliente + fecha ya se autoguarda y cada cambio se persiste.

## Rutas

- `/admin/pedidos/nuevo` → crea un borrador vacío al entrar y redirige inmediatamente a `/admin/pedidos/$id`.
- `/admin/pedidos/$id` → la pantalla unificada (carrito, info, pagos, documentos).
- `/admin/pedidos` → la tabla actual; el botón "Nuevo pedido" navega a `/nuevo` y cada fila linkea al detalle (en lugar de abrir el sheet).

## Layout (inspiración Booqable, mobile 402px y desktop)

```
┌─ Header sticky ────────────────────────────────┐
│  ← Pedidos    Pedido #501  [Borrador ▾]  ···   │
├─ Tabs ─────────────────────────────────────────┤
│  🛒 Carrito   ⓘ Info   💳 Pagos   📄 Docs     │
├─ Tab content (scrollable) ─────────────────────┤
│  ...                                           │
├─ Footer sticky ────────────────────────────────┤
│  [Editar]  [Pagar]            [Confirmar →]   │
└────────────────────────────────────────────────┘
```

- **Tab Carrito**: lista de líneas con thumbnail (placeholder svg por ahora), badge cantidad, nombre, "X disponibles", precio. Sub-items de kit indentados sin thumbnail. Al final: subtotal, "Agregar descuento" → input %, total. FAB "+ Agregar equipo" abre buscador.
- **Tab Info**: cliente (autocompletado + alta rápida), fechas desde/hasta + jornadas, notas internas.
- **Tab Pagos**: total, monto pagado, lista de pagos, botón "Registrar pago".
- **Tab Documentos**: links a presupuesto/remito PDF (placeholders, ya existen en backend).
- **Footer**: acciones contextuales por estado:
  - `borrador` → "Confirmar presupuesto"
  - `presupuesto` → "Confirmar pedido"
  - `confirmado` → "Marcar retirado"
  - `retirado` → "Marcar devuelto"
  - Siempre: menú ··· con "Cancelar" / "Eliminar".

## Autoguardado

- Al entrar a `/nuevo` se llama a `adminApi.createPedido({ estado: "borrador", items: [], cliente_adhoc: { nombre: "Sin nombre" } })` y se redirige.
- Cada cambio (cliente, fechas, item add/remove, qty, precio, descuento, notas) dispara un `useMutation` con debounce de 600ms que llama a un nuevo `adminApi.patchPedido(id, partial)`. Indicador "Guardando…/Guardado" arriba a la derecha.
- Si la conexión falla → toast de error y se reintenta. Sin pérdida de datos en el cliente (estado local + cola).

## Cambios en backend API client (`src/lib/admin/api.ts`)

- Añadir `patchPedido(id, partial)` que mande `PATCH /alquileres/{id}` con campos parciales (cliente, fechas, items, descuento, notas).  
  Si el backend hoy solo soporta cambio de estado (`PedidoEstado` schema), usar la ruta existente para estado y armar endpoints granulares (`/items` add/remove/update, `/cliente`, `/fechas`) reutilizando lo que haya. Donde no exista, crear un wrapper que haga `DELETE` + `POST` del pedido como fallback (solo en estado borrador).
- No tocar Supabase: el catálogo y los pedidos viven en el FastAPI de Railway. La tabla `orders` de Supabase es del lado cliente público y queda intacta.

## Componentes nuevos (`src/components/admin/pedido/`)

- `PedidoPage.tsx` — shell con header, tabs, footer sticky, indicador de autoguardado.
- `tabs/CarritoTab.tsx` — lista, agregar equipo (sheet con buscador y disponibilidad), descuento.
- `tabs/InfoTab.tsx` — cliente + fechas + notas (reutiliza autocompletado y kits del wizard actual).
- `tabs/PagosTab.tsx` — usa endpoints de pagos existentes (`agregar_pago`, `list_pagos`).
- `tabs/DocumentosTab.tsx` — links a PDFs.
- `usePedidoDraft.ts` — hook que envuelve estado + autoguardado debounced + invalidación de queries.

## Migración

1. Crear las nuevas rutas y componentes manteniendo los viejos vivos.
2. Cuando esté funcionando, reemplazar el botón "Nuevo pedido" y el click de fila en `pedidos.tsx`.
3. Borrar `NuevoPedidoWizard.tsx` y `PedidoDetailSheet.tsx`.
4. Actualizar memoria (`mem://features/backoffice-migration.md`) marcando esta fase y su decisión de UX.

## Fuera de alcance (queda para después)

- Tabs Pagos y Documentos pueden quedar como stubs funcionales mínimos en esta fase si la lógica de pagos del backend necesita más trabajo — confirmamos en build si lo dejamos completo o como placeholder.
- Imágenes reales de equipos (siguen los SVG inline del front público).
- Atajos de teclado, duplicar pedido, multi-select en carrito.
