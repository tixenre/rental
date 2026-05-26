/**
 * cart-total.ts — Cálculo único del total del carrito público.
 *
 * Fuente de verdad para los tres consumidores del carrito en armado
 * (CartDrawer desktop, CartSheet mobile, CartMiniBar). Tener UNA sola
 * implementación garantiza que el mismo carrito muestre el mismo total
 * en celu, compu y barra inferior.
 *
 * Modelo:
 *   subtotal     = Σ(pricePerDay × qty) × jornadas
 *   descJornPct  = jornadas > 0 ? interpolarDescuento(puntos, jornadas) : 0
 *   descCliPct   = cliente.descuento ?? 0
 *   descAplicado = max(descJornPct, descCliPct)   // no acumulativos
 *   descOrigen   = "cliente" si gana cliente (empate incluido), si no
 *                  "jornadas", si no "ninguno"
 *   neto         = subtotal − round(subtotal × descAplicado / 100)
 *   iva          = perfil = "responsable_inscripto" ? round(neto × 0.21) : 0
 *   total        = neto + iva
 */

import { interpolarDescuento, type DescuentoJornada } from "@/lib/api";
import { aplicaIva, IVA_RATE, type PerfilImpuestos } from "@/lib/iva";

export type CartLine = { pricePerDay: number; qty: number };

export type DescuentoOrigen = "cliente" | "jornadas" | "ninguno";

export type CartTotal = {
  /** Suma pricePerDay × qty por línea (sin multiplicar por jornadas). */
  subtotalPorJornada: number;
  /** Jornadas usadas en el cómputo. */
  jornadas: number;
  /** Subtotal del período antes de descuentos: subtotalPorJornada × jornadas. */
  subtotal: number;
  /** Porcentaje de descuento aplicado (0..100). */
  descuentoPct: number;
  /** Cuál descuento ganó (o "ninguno" si ambos son 0). */
  descuentoOrigen: DescuentoOrigen;
  /** Monto del descuento aplicado (redondeado). */
  descuentoMonto: number;
  /** Subtotal − descuento. Base sobre la que se calcula IVA. */
  totalNeto: number;
  /** IVA aplicado (0 si el perfil no es responsable_inscripto). */
  iva: number;
  /** true si se sumó IVA (perfil = responsable_inscripto). */
  conIva: boolean;
  /** Total final que ve el cliente. */
  total: number;
};

export function computeCartTotal(args: {
  lines: CartLine[];
  jornadas: number;
  descuentosPuntos: DescuentoJornada[];
  perfilImpuestos: PerfilImpuestos | null | undefined;
  descuentoClientePct: number | null | undefined;
}): CartTotal {
  const { lines, descuentosPuntos, perfilImpuestos, descuentoClientePct } = args;

  const subtotalPorJornada = lines.reduce((s, { pricePerDay, qty }) => s + pricePerDay * qty, 0);
  const jornadas = Math.max(0, args.jornadas);
  const subtotal = subtotalPorJornada * jornadas;

  const descJornPct = jornadas > 0 ? interpolarDescuento(descuentosPuntos, jornadas) : 0;
  const descCliPct = Math.max(0, descuentoClientePct ?? 0);

  // No acumulativos: gana el de mayor valor. En empate gana cliente
  // (es una atención manual del dueño — comunica mejor que el genérico
  // de jornadas).
  let descuentoPct: number;
  let descuentoOrigen: DescuentoOrigen;
  if (descCliPct === 0 && descJornPct === 0) {
    descuentoPct = 0;
    descuentoOrigen = "ninguno";
  } else if (descCliPct >= descJornPct) {
    descuentoPct = descCliPct;
    descuentoOrigen = "cliente";
  } else {
    descuentoPct = descJornPct;
    descuentoOrigen = "jornadas";
  }

  const descuentoMonto = Math.round((subtotal * descuentoPct) / 100);
  const totalNeto = subtotal - descuentoMonto;

  const conIva = aplicaIva(perfilImpuestos);
  const iva = conIva ? Math.round(totalNeto * IVA_RATE) : 0;
  const total = totalNeto + iva;

  return {
    subtotalPorJornada,
    jornadas,
    subtotal,
    descuentoPct,
    descuentoOrigen,
    descuentoMonto,
    totalNeto,
    iva,
    conIva,
    total,
  };
}

/** Etiqueta de la fila de descuento en el UI. */
export function descuentoLabel(origen: DescuentoOrigen, jornadas: number): string {
  if (origen === "jornadas") {
    return `Descuento jornadas (${jornadas} ${jornadas === 1 ? "jornada" : "jornadas"})`;
  }
  if (origen === "cliente") return "Descuento cliente";
  return "";
}
