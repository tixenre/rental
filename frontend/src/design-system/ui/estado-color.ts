import type { EstadoPedido } from "./types";

/**
 * Mapa único de color (bg/text/border) + label por estado de pedido — paleta
 * de marca Rambla. Fuente única del repo: `EstadoBadge` la consume para el
 * chip con forma de pill; `estadoClase` la expone para consumidores que
 * necesitan el color SIN esa forma (ej. la barra del calendario admin).
 * Nunca reimplementar este mapeo aparte — un color nuevo entra acá.
 *
 * Separado de `EstadoBadge.tsx` (que solo puede exportar el componente, por
 * Fast Refresh) — mismo patrón que separar un hook de sus componentes.
 */
export const ESTADO_MAP: Record<EstadoPedido, { label: string; cls: string }> = {
  borrador: {
    label: "Borrador",
    cls: "bg-muted text-muted-foreground border-transparent",
  },
  presupuesto: {
    label: "Presupuesto",
    cls: "bg-azul/10 text-azul-ink border-azul/30",
  },
  solicitado: {
    label: "Solicitado",
    cls: "bg-amber/15 text-ink border-amber/50",
  },
  confirmado: {
    label: "Confirmado",
    cls: "bg-verde/10 text-verde-ink border-verde/30",
  },
  retirado: {
    label: "Retirado",
    cls: "bg-verde/20 text-verde-ink border-verde/40",
  },
  entregado: {
    label: "Entregado",
    cls: "bg-verde/20 text-verde-ink border-verde/40",
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

/** Clases de color (bg/text/border) del estado — sin la forma de pill. */
export function estadoClase(estado: EstadoPedido | string): string {
  return (ESTADO_MAP[estado as EstadoPedido] ?? ESTADO_MAP.borrador).cls;
}
