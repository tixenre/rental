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

import { cn } from "@/lib/utils";
import { fmtArs } from "@/lib/format";
import type { EstadoPedido } from "./types";

type PagoTone = { label: string; cls: string };

// Pre-confirmación = todavía es cotización, no hay deuda real que cobrar.
const PRE_CONFIRM: string[] = ["borrador", "presupuesto", "solicitado", "cancelado"];

/** Estado de pago a mostrar (o null si no aplica). */
function pagoEstado(pagado: number, total: number, estado: EstadoPedido | string): PagoTone | null {
  const saldo = Math.max(0, total - pagado);
  if (total <= 0) return null;
  if (pagado >= total) return { label: "Pagado", cls: "bg-verde/10 text-verde border-verde/30" };
  if (PRE_CONFIRM.includes(estado)) {
    if (pagado > 0)
      return { label: `Seña ${fmtArs(pagado)}`, cls: "bg-amber/15 text-ink border-amber/40" };
    return null;
  }
  // Confirmado en adelante con saldo → mostrar lo que falta cobrar.
  const urgente = estado === "retirado" || estado === "entregado";
  return {
    label: `Debe ${fmtArs(saldo)}`,
    cls: urgente
      ? "bg-destructive/10 text-destructive border-destructive/30"
      : "bg-amber/15 text-ink border-amber/40",
  };
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
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium",
        tag.cls,
        className,
      )}
    >
      {tag.label}
    </span>
  );
}
