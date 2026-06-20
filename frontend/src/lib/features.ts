/**
 * Feature flags de la app — apagar/encender features desde un solo lugar, reversible.
 */

/**
 * Modificación de pedidos por el cliente (solicitudes de cambio de fechas/items
 * sobre un pedido confirmado, desde el portal del cliente).
 *
 * PAUSADO a pedido del dueño — ver #750. Poner en `true` para reactivar:
 * vuelve el botón "Modificar" en `cliente.portal` y se desbloquea la ruta
 * `/cliente/pedidos/$id/editar`. El motor de solicitudes en el backend sigue intacto.
 */
export const MODIFICAR_PEDIDOS_HABILITADO = false;
