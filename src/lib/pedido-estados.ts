/**
 * Tipo canónico de estados de pedido — fuente única para todo el repo.
 *
 * Admin y portal cliente importan desde acá.
 * El orden refleja el ciclo de vida típico de un pedido.
 */
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

/** Label del CTA del "siguiente paso feliz" — compartido entre lista y editor de pedidos. */
export const PEDIDO_NEXT_LABEL: Partial<Record<EstadoPedido, string>> = {
  borrador: "Presupuestar",
  presupuesto: "Confirmar pedido",
  solicitado: "Confirmar pedido",
  confirmado: "Marcar retirado",
  retirado: "Registrar devolución",
  entregado: "Registrar devolución",
  devuelto: "Cobrar saldo y finalizar",
};
