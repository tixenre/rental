import { cn } from "@/lib/utils";
import { Pill } from "./Pill";
import type { EstadoPedido } from "./types";
import { ESTADO_MAP } from "./estado-color";

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
 * El prop opcional `label` overridea el texto visible; el color sigue saliendo
 * del map por `estado` (la paleta de marca documentada).
 *
 * El mapa de color vive en `./estado-color.ts` (Fast Refresh exige que este
 * archivo solo exporte el componente) — `estadoClase` de ese módulo es la
 * puerta para consumidores que necesitan el color sin la forma de pill.
 */
export function EstadoBadge({
  estado,
  label: labelOverride,
  className,
}: {
  estado: EstadoPedido | string;
  /** Override del texto visible. El color sigue saliendo del map por `estado`. */
  label?: string;
  className?: string;
}) {
  const { label: mappedLabel, cls } = ESTADO_MAP[estado as EstadoPedido] ?? {
    label: estado,
    cls: "bg-muted text-muted-foreground border-transparent",
  };
  const label = labelOverride ?? mappedLabel;
  // La forma del pill sale del primitivo `Pill`; el color sigue saliendo del map
  // por `estado` (paleta de marca documentada). El contraste de estos tints es
  // una decisión visual aparte (ver Filosofía de diseño en DESIGN_SYSTEM.md).
  return <Pill className={cn(cls, className)}>{label}</Pill>;
}
