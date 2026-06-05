import { cn } from "@/lib/utils";
import type { EstadoPedido } from "./types";

export type { EstadoPedido };

/**
 * EstadoBadge — chip de estado para pedidos, paleta de marca Rambla.
 *
 * Versión con paleta secundaria oficial (--rosa/azul/verde/naranja).
 *
 * Source of truth única del repo desde PR E1 — la versión vieja en
 * `src/components/rental/EstadoBadge.tsx` (que usaba `bg-blue-50` Tailwind
 * genéricos) fue eliminada al migrar `cliente.portal.tsx`.
 *
 * Admin (`/admin/pedidos`, `/admin/pedidos/$id`) también la consume (PR E2).
 * Usa el prop opcional `label` para preservar su alias visible
 * "presupuesto → Solicitado": el texto se overridea, el color sigue saliendo
 * del map por `estado` (presupuesto → azul, la paleta de marca documentada).
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
  label: labelOverride,
  className,
}: {
  estado: EstadoPedido | string;
  /** Override del texto visible. El color sigue saliendo del map por `estado`.
   *  Lo usa el admin para mostrar "Solicitado" sobre el estado `presupuesto`. */
  label?: string;
  className?: string;
}) {
  const { label: mappedLabel, cls } = ESTADO_MAP[estado as EstadoPedido] ?? {
    label: estado,
    cls: "bg-muted text-muted-foreground border-transparent",
  };
  const label = labelOverride ?? mappedLabel;
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
