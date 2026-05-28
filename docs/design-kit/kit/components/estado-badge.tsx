import { cn } from "./lib/cn";
import type { EstadoPedido } from "../types/equipment";

export type { EstadoPedido };

/**
 * EstadoBadge — chip de estado para pedidos.
 *
 * Mapeo de estados al ciclo de vida real de un pedido en Rambla:
 *
 *   borrador     → muted          (cliente todavía editando)
 *   presupuesto  → azul soft      (cotizado, esperando respuesta)
 *   solicitado   → amber soft     (cliente confirmó, en cola del operador)
 *   confirmado   → verde soft     (operador aprobó)
 *   retirado     → verde fuerte   (en posesión del cliente)
 *   entregado    → verde fuerte   (alias de retirado en algunas vistas)
 *   devuelto     → muted          (cerrado OK)
 *   finalizado   → muted          (cerrado OK, archivado)
 *   cancelado    → destructive    (no procedió)
 *
 * Los tokens usan la paleta secundaria oficial (--rosa/azul/naranja/verde).
 * Si pasás un estado desconocido, cae a muted con el string tal cual.
 *
 * @example
 *   <EstadoBadge estado="solicitado" />
 *   <EstadoBadge estado="confirmado" />
 */

const ESTADO_MAP: Record<EstadoPedido, { label: string; cls: string }> = {
  borrador: {
    label: "Borrador",
    cls: "bg-muted text-muted-foreground border-transparent",
  },
  presupuesto: {
    label: "Presupuesto",
    cls: "bg-azul/10 text-azul border-azul/30",
  },
  solicitado: {
    label: "Solicitado",
    cls: "bg-amber/15 text-ink border-amber/50",
  },
  confirmado: {
    label: "Confirmado",
    cls: "bg-verde/10 text-verde border-verde/30",
  },
  retirado: {
    label: "Retirado",
    cls: "bg-verde/20 text-verde border-verde/40",
  },
  entregado: {
    label: "Entregado",
    cls: "bg-verde/20 text-verde border-verde/40",
  },
  devuelto: {
    label: "Devuelto",
    cls: "bg-muted text-muted-foreground border-hairline",
  },
  finalizado: {
    label: "Finalizado",
    cls: "bg-muted text-muted-foreground border-hairline",
  },
  cancelado: {
    label: "Cancelado",
    cls: "bg-destructive/10 text-destructive border-destructive/30",
  },
};

export function EstadoBadge({
  estado,
  className,
}: {
  estado: EstadoPedido | string;
  className?: string;
}) {
  const { label, cls } = ESTADO_MAP[estado as EstadoPedido] ?? {
    label: estado,
    cls: "bg-muted text-muted-foreground border-transparent",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 font-sans text-[10px] font-medium",
        cls,
        className,
      )}
    >
      {label}
    </span>
  );
}
