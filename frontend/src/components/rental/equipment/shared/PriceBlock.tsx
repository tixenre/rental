import { formatARS } from "@/lib/format";
import { priceBreakdown } from "@/lib/pricing";
import { cn } from "@/lib/utils";

interface PriceBlockProps {
  /** Precio por jornada del equipo (base, sin descuentos). */
  perDay: number;
  /** Jornadas del período seleccionado. 0 = sin fechas. */
  jornadas?: number;
  /** Unidades en el carrito. Default 1. */
  qty?: number;
  /** Si el cliente es responsable inscripto (agrega "+IVA" al label). */
  conIva?: boolean;
  /** Alineación del bloque. Grid/mobile: left. Lista desktop: right. */
  align?: "left" | "right";
  /**
   * Tamaño del amount principal.
   * lg = 19px (grid card) · md = 17px (lista desktop) · sm = 14px (mobile)
   */
  size?: "lg" | "md" | "sm";
  /**
   * Compacto: oculta la 3ª línea ("$X / jornada") cuando se muestra el total
   * del período. Para filas densas (lista mobile colapsada) donde el ancho es
   * escaso; el desglose completo queda en el panel expandido / ficha.
   */
  compact?: boolean;
  className?: string;
}

/**
 * Bloque de precio — asset compartido de la librería `equipment/shared`.
 *
 * Regla de jerarquía:
 * - Sin fechas / 1 jornada: muestra precio / jornada.
 * - Con fechas y > 1 jornada: TOTAL del período en grande + precio / jornada
 *   secundario abajo.
 *
 * El total sale SIEMPRE de `priceBreakdown()` (@/lib/pricing) — nunca se
 * multiplica a mano — para que el día que entren descuentos (#73) no haya que
 * tocar este componente. Fuente: font-mono font-semibold tabular-nums (nunca
 * font-display: Champ Black no escala bien por debajo de ~28px).
 */
export function PriceBlock({
  perDay,
  jornadas = 0,
  qty = 1,
  conIva = false,
  align = "left",
  size = "md",
  compact = false,
  className,
}: PriceBlockProps) {
  const showPeriodTotal = jornadas > 1;
  const { total } = priceBreakdown(perDay, jornadas, qty);
  const ivaSuffix = conIva ? " +IVA" : "";

  const amountClass = size === "lg" ? "text-[19px]" : size === "md" ? "text-[17px]" : "text-[14px]";

  return (
    <div
      className={cn(
        "flex flex-col gap-[1px]",
        align === "right" && "items-end text-right",
        className,
      )}
    >
      {/* Número protagonista */}
      <span
        className={cn(
          "font-mono font-semibold tabular-nums text-ink leading-none whitespace-nowrap",
          amountClass,
        )}
      >
        {showPeriodTotal ? formatARS(total) : formatARS(perDay)}
      </span>

      {/* Label secundario */}
      <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground leading-none">
        {showPeriodTotal ? `${jornadas} jornadas` : `/ jornada${ivaSuffix}`}
      </span>

      {/* Por-jornada cuando mostramos total del período (oculto en compact) */}
      {showPeriodTotal && !compact && (
        <span className="font-mono text-[11px] tabular-nums text-muted-foreground leading-none whitespace-nowrap">
          {formatARS(perDay)} / jornada{ivaSuffix}
        </span>
      )}
    </div>
  );
}
