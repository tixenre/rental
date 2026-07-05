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
  /**
   * Compacto: oculta la 3ª línea ("$X / jornada") cuando se muestra el total
   * del período. Para filas densas (lista mobile colapsada) donde el ancho es
   * escaso; el desglose completo queda en el panel expandido / ficha.
   */
  compact?: boolean;
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
 * Regla de jerarquía:
 * - Sin fechas / 1 jornada: muestra precio / jornada.
 * - Con fechas y > 1 jornada: TOTAL del período en grande + precio / jornada
 *   secundario abajo.
 *
 * El total sale SIEMPRE de `priceBreakdown()` (@/lib/pricing) — nunca se
 * multiplica a mano. Con descuento (`perDayFinal` < `perDay`), se llama DOS
 * veces (original y final) — sigue siendo la misma multiplicación por
 * jornadas/cantidad de siempre, el % ya viene resuelto del backend. Fuente:
 * font-mono font-semibold tabular-nums (nunca font-display: Champ Black no
 * escala bien por debajo de ~28px). Tachado/destacado reusa el mismo patrón
 * de `CartDrawerView.tsx` (línea de carrito con descuento) — no un componente
 * nuevo.
 */
export function PriceBlock({
  perDay,
  jornadas = 0,
  unidad = "jornada",
  qty = 1,
  conIva = false,
  align = "left",
  size = "md",
  compact = false,
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

  const discountLabel =
    descuentoOrigen === "cliente"
      ? `−${descuentoPct}% tu descuento`
      : `−${descuentoPct}% por ${jornadas} ${jornadas === 1 ? "día" : "días"}`;

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

      {/* Label secundario */}
      <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground leading-none">
        {showPeriodTotal ? unidadLabel(jornadas, unidad) : `/ ${unidadSingular}${ivaSuffix}`}
      </span>

      {/* Por qué hay descuento — solo cuando lo hay, para que quede claro que
          no es un error de precio (jornadas vs. cliente, nunca los dos). */}
      {hasDiscount && (
        <span className="font-mono text-2xs font-semibold text-verde-ink uppercase tracking-wide leading-none">
          {discountLabel}
        </span>
      )}

      {/* Por-unidad cuando mostramos total del período (oculto en compact) */}
      {showPeriodTotal && !compact && (
        <span className="font-mono text-xs tabular-nums text-muted-foreground leading-none whitespace-nowrap">
          {formatARS(hasDiscount ? perDayFinal : perDay)} / {unidadSingular}
          {ivaSuffix}
        </span>
      )}
    </div>
  );
}
