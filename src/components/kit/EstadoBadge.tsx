import { cn } from "@/lib/utils";
import type { EstadoPedido } from "./types";

export type { EstadoPedido };

/**
 * EstadoBadge — chip de estado para pedidos, paleta de marca Rambla.
 *
 * Source: `docs/design-kit/kit/components/estado-badge.tsx`. Versión del kit
 * con paleta secundaria oficial (--rosa/azul/verde/naranja).
 *
 * Source of truth única del repo desde PR E1 — la versión vieja en
 * `src/components/rental/EstadoBadge.tsx` (que usaba `bg-blue-50` Tailwind
 * genéricos) fue eliminada al migrar `cliente.portal.tsx`.
 *
 * Admin (`/admin/pedidos`, `/admin/pedidos/$id`) sigue con su mapping
 * inline temporalmente — issue #575 trackea la migración con prop
 * `label` para preservar el override de "Solicitado".
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
