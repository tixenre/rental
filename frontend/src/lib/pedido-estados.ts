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

// ── Máquina de estados (espeja ESTADOS_VALIDOS del backend, alquileres.py) ────
// El back-office NO ofrece transiciones que el backend rechazaría. Fuente única
// compartida entre el editor (pedidos.$id) y el panel de detalle (pedidos.index).

/** Secuencia del "camino feliz" para el indicador de progreso (FlowStrip). */
export const FLOW: EstadoPedido[] = [
  "presupuesto",
  "confirmado",
  "retirado",
  "devuelto",
  "finalizado",
];

/** Transiciones permitidas por estado (espeja el backend). */
export const TRANSICIONES: Partial<Record<EstadoPedido, EstadoPedido[]>> = {
  borrador: ["presupuesto", "cancelado"],
  presupuesto: ["confirmado", "cancelado"],
  solicitado: ["confirmado", "cancelado"], // estado del portal → se confirma igual
  confirmado: ["retirado", "cancelado"],
  retirado: ["devuelto", "cancelado"],
  entregado: ["devuelto", "cancelado"], // estado del portal
  devuelto: ["finalizado"],
  finalizado: [],
  cancelado: [],
};

export const transiciones = (e: EstadoPedido): EstadoPedido[] => TRANSICIONES[e] ?? [];

/** Datos mínimos de un pedido para evaluar bloqueos de transición (evita acoplar al tipo Pedido). */
export type PedidoTransicionable = {
  estado: EstadoPedido;
  fecha_desde?: string | null;
  fecha_hasta?: string | null;
  items?: { length: number } | null;
};

/** Motivo por el que un destino está bloqueado (faltan fechas / sin equipos) — espeja la validación del backend. */
export function blockReason(p: PedidoTransicionable, target: EstadoPedido): string | null {
  const needs: EstadoPedido[] = ["confirmado", "retirado", "devuelto", "finalizado"];
  if (needs.includes(target)) {
    if (!p.fecha_desde || !p.fecha_hasta) return "faltan fechas";
    if (!p.items?.length) return "sin equipos";
  }
  return null;
}

/** Próximo paso "feliz" (no-cancelar) + label + motivo de bloqueo; null si es estado terminal. */
export function nextStep(
  p: PedidoTransicionable,
): { target: EstadoPedido; label: string; blocked: string | null } | null {
  const t = transiciones(p.estado).filter((x) => x !== "cancelado");
  if (!t.length) return null;
  const target = t[0];
  return {
    target,
    label: PEDIDO_NEXT_LABEL[p.estado] ?? "Avanzar",
    blocked: blockReason(p, target),
  };
}
