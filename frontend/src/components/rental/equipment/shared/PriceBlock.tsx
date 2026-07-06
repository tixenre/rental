import { formatARS, UNIDADES, unidadLabel, type Unidad } from "@/lib/format";
import { priceBreakdown } from "@/lib/pricing";
import { cn } from "@/lib/utils";

interface PriceBlockProps {
  /** Precio por unidad (jornada/hora) del equipo (base, sin descuentos). */
  perDay: number;
  /** Unidades del período seleccionado (jornadas/horas). 0 = sin fechas. */
  jornadas?: number;
  /**
   * Unidad de la tarifa (default `jornada`, alquiler). `hora` para el estudio.
   * El término y su plural salen de `UNIDADES` (fuente única) — no hardcodear.
   */
  unidad?: Unidad;
  /** Cantidad en el carrito. Default 1. */
  qty?: number;
  /** Si el cliente es responsable inscripto (agrega "+IVA" al label). */
  conIva?: boolean;
  /** Alineación del bloque. Grid/mobile: left. Lista desktop: right. */
  align?: "left" | "right";
  /**
   * Tamaño del amount principal.
   * lg = 19px (grid card) · md = 17px (lista desktop) · sm = 15px (mobile)
   */
  size?: "lg" | "md" | "sm";
  className?: string;
  /**
   * Precio por unidad YA CON el descuento ganador aplicado (cliente vs.
   * jornadas, no acumulable — resuelto por el backend, `precio_jornada_final`
   * de `/api/equipos`). `undefined`/igual a `perDay` → sin descuento, se
   * muestra como siempre. MEMORIA 2026-07-05: el front NO calcula el %, solo
   * multiplica por jornadas/cantidad — la MISMA operación que ya hacía.
   */
  perDayFinal?: number;
  /** % del descuento aplicado (informativo, para el label — "−15% por 5 días"). */
  descuentoPct?: number;
  /** Quién ganó el descuento — cambia el texto del label. */
  descuentoOrigen?: "cliente" | "jornadas" | null;
}

/**
 * Bloque de precio — asset compartido de la librería `equipment/shared`.
 *
 * UN SOLO precio protagonista (nunca dos números compitiendo): sin fechas o
 * 1 jornada → precio/jornada; con fechas y > 1 jornada → TOTAL del período.
 * La línea de "$X / jornada" se sacó (2026-07-06): con el tachado + el label
 * del descuento ya alcanza, una 3ª cifra sumaba ruido sin agregar nada que el
 * dueño necesitara ver ahí (feedback en vivo sobre el primer diseño).
 *
 * El total sale SIEMPRE de `priceBreakdown()` (@/lib/pricing) — nunca se
 * multiplica a mano. Con descuento (`perDayFinal` < `perDay`), se llama DOS
 * veces (original y final) — sigue siendo la misma multiplicación por
 * jornadas/cantidad de siempre, el % ya viene resuelto del backend. Fuente:
 * font-mono font-semibold tabular-nums (nunca font-display: Champ Black no
 * escala bien por debajo de ~28px). Tachado/destacado reusa el mismo patrón
 * de `CartDrawerView.tsx` (línea de carrito con descuento) — no un componente
 * nuevo. La línea de contexto (jornadas + motivo del descuento) es UNA sola,
 * no dos separadas.
 */
export function PriceBlock({
  perDay,
  jornadas = 0,
  unidad = "jornada",
  qty = 1,
  conIva = false,
  align = "left",
  size = "md",
  className,
  perDayFinal,
  descuentoPct = 0,
  descuentoOrigen = null,
}: PriceBlockProps) {
  const unidadSingular = UNIDADES[unidad].singular;
  const showPeriodTotal = jornadas > 1;
  const hasDiscount = !!perDayFinal && perDayFinal < perDay && descuentoPct > 0;

  const { total: totalOriginal } = priceBreakdown(perDay, jornadas, qty);
  const { total: totalFinal } = hasDiscount
    ? priceBreakdown(perDayFinal, jornadas, qty)
    : { total: totalOriginal };

  const amountOriginal = showPeriodTotal ? totalOriginal : perDay;
  const amountFinal = showPeriodTotal ? totalFinal : hasDiscount ? perDayFinal : perDay;
  const ivaSuffix = conIva ? " +IVA" : "";

  const amountClass = size === "lg" ? "text-[19px]" : size === "md" ? "text-[17px]" : "text-15"; // eslint-disable-line no-restricted-syntax -- tamaños ópticos del precio: escala entre text-15 y text-xl calibrada para moneda

  // Una sola línea de contexto: con descuento, jornadas + motivo van juntos
  // ("5 días · −15%" / "tu descuento · −15%"); sin descuento, la unidad sola.
  const contextLabel = hasDiscount
    ? descuentoOrigen === "cliente"
      ? `Tu descuento · −${descuentoPct}%`
      : `${jornadas} ${jornadas === 1 ? "día" : "días"} · −${descuentoPct}%`
    : showPeriodTotal
      ? unidadLabel(jornadas, unidad)
      : `/ ${unidadSingular}${ivaSuffix}`;

  return (
    <div
      className={cn(
        "flex flex-col gap-[1px]",
        align === "right" && "items-end text-right",
        className,
      )}
    >
      {/* Número protagonista (+ original tachado al lado, si hay descuento) */}
      <div className={cn("flex items-baseline gap-1.5", align === "right" && "flex-row-reverse")}>
        <span
          className={cn(
            "font-mono font-semibold tabular-nums leading-none whitespace-nowrap",
            hasDiscount ? "text-verde-ink" : "text-ink",
            amountClass,
          )}
        >
          {formatARS(amountFinal)}
        </span>
        {hasDiscount && (
          <span className="font-mono text-xs tabular-nums text-muted-foreground/60 line-through leading-none whitespace-nowrap">
            {formatARS(amountOriginal)}
          </span>
        )}
      </div>

      {/* Única línea de contexto (jornadas y/o motivo del descuento) */}
      <span
        className={cn(
          "font-mono text-xs uppercase tracking-widest leading-none",
          hasDiscount ? "font-semibold text-verde-ink" : "text-muted-foreground",
        )}
      >
        {contextLabel}
      </span>
    </div>
  );
}
