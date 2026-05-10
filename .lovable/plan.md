
## Objetivo

Que cada cliente pueda descargar **Remito**, **Contrato** y **Albarán** de sus pedidos desde `/mis-pedidos/[id]`, reutilizando los generadores de PDF que ya existen en el backend FastAPI (`backend/pdf.py`).

## Reglas de disponibilidad (por estado)

| Documento | Disponible desde |
|---|---|
| Remito (resumen del pedido) | `confirmado` |
| Contrato de alquiler | `confirmado` |
| Albarán de entrega/devolución | `entregado` (entrega) y `devuelto` (devolución completa) |

Antes de esos estados, el documento aparece en la UI **deshabilitado** con un tooltip explicando qué falta (ej: "Disponible cuando confirmemos el pedido").

## Backend (FastAPI)

Nuevos endpoints públicos del cliente en `backend/routes/cliente_portal.py` (montado en `/api/cliente`), que reutilizan los renderers existentes (`_pedido_html`, `_contrato_html`, `_albaran_html`, `_render_pdf`):

- `GET /api/cliente/pedidos/{id}/remito.pdf`
- `GET /api/cliente/pedidos/{id}/contrato.pdf`
- `GET /api/cliente/pedidos/{id}/albaran.pdf`

Cada endpoint:
1. Valida el JWT de Supabase (middleware ya existente del portal cliente).
2. Verifica que el pedido pertenezca al `user_id` del token (404 si no).
3. Verifica el estado mínimo según la tabla anterior (403 con detalle si no corresponde).
4. Retorna el PDF como `application/pdf` con `Content-Disposition: inline; filename=...` para previsualizar y descargar.

Además, el `GET /api/cliente/pedidos/{id}` (detalle) devuelve un nuevo campo `documentos_disponibles: { remito: bool, contrato: bool, albaran: bool }` para que el frontend sepa qué habilitar sin tener que duplicar la lógica de estados.

## Frontend

### `src/lib/orders.ts`
- Extender el tipo de detalle con `documentosDisponibles`.
- Agregar helper `getOrderDocumentUrl(orderId, tipo)` que arme la URL absoluta al backend con el header de auth (vía `authedFetch` → blob → `URL.createObjectURL`) para descargar sin exponer el token en query string.

### `src/routes/_auth/mis-pedidos/$id.tsx`
Nueva sección **"Documentos"** entre "Equipos" y "Solicitar un cambio":

```text
┌─ Documentos ────────────────────────────┐
│ 📄 Remito         [Ver] [Descargar]    │
│ 📄 Contrato       [Ver] [Descargar]    │
│ 📄 Albarán        Disponible al entregar│
└─────────────────────────────────────────┘
```

- Usa el mismo lenguaje visual de las otras tarjetas (`rounded-xl border hairline bg-surface`, header en font-mono uppercase).
- Botones deshabilitados con tooltip cuando el documento no está disponible.
- "Ver" abre el PDF en una pestaña nueva; "Descargar" fuerza la descarga (mismo blob, `<a download>`).
- Estado de carga por documento (spinner mientras se baja el blob).

### `src/routes/_auth/mis-pedidos/index.tsx`
Pequeño badge `📄 3` en la fila del pedido si hay documentos disponibles, para que se note desde el listado.

## Detalles técnicos

- Reuso 100% de `_pedido_html`, `_contrato_html`, `_albaran_html` y `_render_pdf` en `backend/pdf.py`. No se tocan los templates.
- El back-office sigue usando los endpoints `/alquileres/{id}/{pdf|albaran|contrato}` ya existentes; los nuevos endpoints del cliente son una capa paralela con auth distinta y validación de ownership/estado.
- No se persisten archivos: cada descarga se renderiza on-demand. Si en el futuro queremos cache/firmas, se añade `documentos_generados` con storage; por ahora no hace falta.
- Memory: agregar nota en `mem://index.md` sobre la regla "documentos visibles según estado".

## Out of scope (para iteraciones futuras)

- Firma digital del cliente sobre el contrato.
- Versionado / historial de PDFs (re-emisiones cuando cambia el pedido).
- Envío automático por email al cambiar de estado (esto se cubrirá cuando hagamos la feature de emails transaccionales).
