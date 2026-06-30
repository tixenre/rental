/**
 * PagoBadge — chip de estado de pago, fuente única del repo.
 *
 * Hermano de `EstadoBadge`: mientras ese muestra el estado del pedido, este
 * muestra la cobranza con el monto (idea tomada de cómo Booqable hace visible
 * el "Estado del pago"). Pensado para reusar en cualquier superficie que liste
 * pedidos (admin, portal cliente, dashboards).
 *
 * Devuelve `null` cuando no hay nada útil que mostrar (cotización sin seña, o
 * pedido sin monto) — el caller no necesita un placeholder.
 */

import { fmtArs } from "@/lib/format";
import { Pill, type PillTone } from "./Pill";
import type { EstadoPedido } from "./types";

type PagoTag = { label: string; tone: PillTone };

// Pre-confirmación = todavía es cotización, no hay deuda real que cobrar.
const PRE_CONFIRM: string[] = ["borrador", "presupuesto", "solicitado", "cancelado"];

/** Estado de pago a mostrar (o null si no aplica). */
function pagoEstado(pagado: number, total: number, estado: EstadoPedido | string): PagoTag | null {
  const saldo = Math.max(0, total - pagado);
  if (total <= 0) return null;
  if (pagado >= total) return { label: "Pagado", tone: "success" };
  if (PRE_CONFIRM.includes(estado)) {
    if (pagado > 0) return { label: `Seña ${fmtArs(pagado)}`, tone: "warning" };
    return null;
  }
  // Confirmado en adelante con saldo → mostrar lo que falta cobrar.
  const urgente = estado === "retirado" || estado === "entregado";
  return { label: `Debe ${fmtArs(saldo)}`, tone: urgente ? "danger" : "warning" };
}

export function PagoBadge({
  pagado,
  total,
  estado,
  className,
}: {
  pagado: number;
  total: number;
  estado: EstadoPedido | string;
  className?: string;
}) {
  const tag = pagoEstado(pagado, total, estado);
  if (!tag) return null;
  return (
    <Pill tone={tag.tone} className={className}>
      {tag.label}
    </Pill>
  );
}
