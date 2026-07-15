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
  // Ciclo de vida por color (2026-07-14): cada etapa activa tiene su propio color
  // de marca, la progresión "avanza" con el pedido. Borrador (provisorio) y
  // Finalizado (definitivo) se distinguen por PESO — borrador punteado sin fondo,
  // finalizado gris sólido con texto oscuro — antes ambos eran el mismo gris.
  borrador: {
    label: "Borrador",
    cls: "bg-transparent text-muted-foreground border-dashed border-muted-foreground/45",
  },
  // `solicitado` (ex-`presupuesto`, renombrado 2026-07-14): el estado inicial. Se
  // MUESTRA "Solicitud" — el cliente lo solicitó, todavía no es un rental
  // confirmado. El documento PDF sigue llamándose "Presupuesto" (es el papel, no
  // el estado). `entregado` es display del portal (hereda el naranja de retirado).
  solicitado: {
    label: "Solicitud",
    cls: "bg-azul/10 text-azul-ink border-azul/30",
  },
  confirmado: {
    label: "Confirmado",
    cls: "bg-verde/10 text-verde-ink border-verde/30",
  },
  retirado: {
    label: "Retirado",
    cls: "bg-naranja/15 text-naranja-ink border-naranja/45",
  },
  entregado: {
    label: "Entregado",
    cls: "bg-naranja/15 text-naranja-ink border-naranja/45",
  },
  devuelto: {
    label: "Devuelto",
    cls: "bg-rosa/15 text-rosa-ink border-rosa/45",
  },
  finalizado: {
    label: "Finalizado",
    cls: "bg-muted text-ink border-muted-foreground/45",
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
