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
