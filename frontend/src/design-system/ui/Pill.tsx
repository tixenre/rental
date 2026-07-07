/**
 * Pill — forma única del chip/pill de estado del repo.
 *
 * Materializa el principio "reusar, no recrear" de la Filosofía de diseño
 * (DESIGN_SYSTEM.md): la forma del pill (rounded-full + border + métricas) y los
 * tonos semánticos viven acá una sola vez. `EstadoBadge` y `PagoBadge` derivan de
 * este primitivo; cualquier badge nuevo también. No copiar las clases del pill a mano.
 */

import { cn } from "@/lib/utils";

/** Tono semántico del pill. */
export type PillTone = "success" | "warning" | "danger" | "info" | "neutral";

const TONE: Record<PillTone, string> = {
  success: "bg-verde/10 text-verde-ink border-verde/30",
  warning: "bg-amber/15 text-ink border-amber/40",
  danger: "bg-destructive/10 text-destructive border-destructive/30",
  info: "bg-azul/10 text-azul-ink border-azul/30",
  neutral: "bg-muted text-muted-foreground border-transparent",
};

const BASE = "inline-flex shrink-0 items-center rounded-full border font-medium";

/** `default` = tamaño estándar (text-xs); `compact` = para tablas/listas muy
 *  densas donde el default rompe el layout (mismo tamaño que antes de la
 *  subida de escala). No usar `compact` por defecto — es la excepción. */
const SIZE: Record<"default" | "compact", string> = {
  default: "px-2 py-0.5 text-xs",
  compact: "px-1.5 py-0.5 text-2xs",
};

export function Pill({
  tone,
  size = "default",
  className,
  children,
}: {
  /** Color por tono semántico. Omitilo y pasá `className` para un color a medida. */
  tone?: PillTone;
  size?: "default" | "compact";
  className?: string;
  children: React.ReactNode;
}) {
  return <span className={cn(BASE, SIZE[size], tone && TONE[tone], className)}>{children}</span>;
}
