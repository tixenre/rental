import type { PedidoEstado } from "@/lib/admin/api";

export function pedidoEstadoVariant(
  e: PedidoEstado,
): "default" | "secondary" | "outline" | "destructive" {
  if (e === "cancelado") return "destructive";
  if (e === "finalizado" || e === "devuelto") return "secondary";
  if (e === "borrador" || e === "presupuesto") return "outline";
  return "default";
}
