import { Pill, type PillTone } from "@/design-system/kit/Pill";
import type { TipoMovimiento } from "@/lib/admin/api";

/**
 * Badges de negocio del back-office — derivan del primitivo `Pill` (ink-on-tint),
 * fuente única de la forma del chip. Acá viven los badges con semántica de dominio
 * (tipo de movimiento, etc.) que mapean un valor del modelo a un tono.
 */

/** Meta por tipo de movimiento: label + tono. Fuente única (la consume el badge Y el filtro). */
// eslint-disable-next-line react-refresh/only-export-components -- meta + badge conviven a propósito (fuente única label+tono); el filtro reusa la meta
export const TIPO_MOVIMIENTO_META: Record<TipoMovimiento, { label: string; tone: PillTone }> = {
  gasto: { label: "Gasto", tone: "danger" }, // plata que sale
  retiro: { label: "Retiro", tone: "warning" }, // socio retira
  transferencia: { label: "Transferencia", tone: "neutral" }, // movimiento interno
  aporte: { label: "Aporte", tone: "success" }, // plata que entra
  ajuste: { label: "Ajuste", tone: "info" },
};

export function TipoMovimientoBadge({ tipo }: { tipo: TipoMovimiento }) {
  const meta = TIPO_MOVIMIENTO_META[tipo] ?? { label: tipo, tone: "neutral" as PillTone };
  return <Pill tone={meta.tone}>{meta.label}</Pill>;
}
