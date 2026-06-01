/**
 * Rambla Rental — tipos compartidos del kit
 * ------------------------------------------------------------
 * Reconstruido para el paquete canónico (en el repo vivía como
 * `src/components/kit/types.ts`). Consumido por EstadoBadge y AddonPills.
 * Mantené esta unión sincronizada con los estados reales de la API de pedidos.
 */

/** Estados de un pedido. El orden refleja el ciclo de vida real. */
export type EstadoPedido =
  | "borrador"
  | "presupuesto"
  | "solicitado"
  | "confirmado"
  | "retirado"
  | "entregado"
  | "devuelto"
  | "finalizado"
  | "cancelado";

/** Item "incluye" mostrado en AddonPills sobre la row de un equipo. */
export interface AddonItem {
  /** id estable para la key (opcional — cae a name si falta). */
  id?: string | number;
  /** Nombre visible del add-on (ej: "Trípode", "Batería extra"). */
  name: string;
  /** Cantidad incluida; solo se renderiza el badge si qty > 1. */
  qty?: number;
}
