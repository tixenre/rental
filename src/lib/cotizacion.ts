/**
 * cotizacion.ts — Cliente del endpoint canónico de cotización (`POST /api/cotizar`).
 *
 * El total del carrito lo calcula EL BACKEND (fuente única,
 * `services/precios.calcular_total`). El front ya NO reimplementa la fórmula:
 * manda los ítems (equipo_id + cantidad) y, si hay, las fechas, y muestra el
 * desglose que devuelve el backend tal cual. Reemplaza al viejo `cart-total.ts`.
 * Ver #617 / #508.
 *
 * Reglas (las decide el backend, no el front):
 *  - Sin fechas → estimado de UNA jornada, sin descuento ni IVA.
 *  - Cliente logueado → su perfil/descuento. Admin → el del `clienteId` que
 *    pase (arma pedidos para terceros). Anónimo / sin cliente → consumidor final.
 */

import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { authedPostJson } from "@/lib/authedFetch";

export type DescuentoOrigen = "cliente" | "jornadas" | "ninguno";

/** Desglose normalizado para el UI (mismas keys que usaba `CartTotal`). */
export type Cotizacion = {
  /** Σ(precio_jornada × cantidad), sin multiplicar por jornadas. */
  subtotalPorJornada: number;
  jornadas: number;
  /** Bruto del período: subtotalPorJornada × jornadas (antes de descuentos). */
  subtotal: number;
  descuentoPct: number;
  descuentoOrigen: DescuentoOrigen;
  descuentoMonto: number;
  /** Neto = subtotal − descuento. Es lo que se PERSISTE en `monto_total`. */
  totalNeto: number;
  /** IVA (0 si el cliente no es responsable_inscripto). */
  iva: number;
  conIva: boolean;
  /** Total a mostrar: neto + IVA. */
  total: number;
};

/** Respuesta cruda del backend (`/api/cotizar`). */
type CotizarResp = {
  jornadas: number;
  subtotal_por_jornada: number;
  descuento_origen: DescuentoOrigen;
  bruto: number;
  descuento_pct: number;
  descuento_monto: number;
  neto: number;
  con_iva: boolean;
  iva_pct: number;
  iva_monto: number;
  total_final: number;
};

export const COTIZACION_VACIA: Cotizacion = {
  subtotalPorJornada: 0,
  jornadas: 1,
  subtotal: 0,
  descuentoPct: 0,
  descuentoOrigen: "ninguno",
  descuentoMonto: 0,
  totalNeto: 0,
  iva: 0,
  conIva: false,
  total: 0,
};

function adaptar(r: CotizarResp): Cotizacion {
  return {
    subtotalPorJornada: r.subtotal_por_jornada,
    jornadas: r.jornadas,
    subtotal: r.bruto,
    descuentoPct: r.descuento_pct,
    descuentoOrigen: r.descuento_origen,
    descuentoMonto: r.descuento_monto,
    totalNeto: r.neto,
    iva: r.iva_monto,
    conIva: r.con_iva,
    total: r.total_final,
  };
}

export type CotizarItemInput = { equipoId: number; cantidad: number };

/**
 * Cotiza el carrito contra el backend. Refetch automático al cambiar ítems o
 * fechas; mantiene el valor anterior mientras recalcula (sin parpadeo).
 * Carrito vacío → devuelve `COTIZACION_VACIA` sin pegarle al backend.
 */
export function useCotizacion(args: {
  items: CotizarItemInput[];
  /** ISO-local `YYYY-MM-DDTHH:MM:00` (usar `toLocalISO`). Sin fechas → estimado. */
  fechaDesde?: string | null;
  fechaHasta?: string | null;
  /** Solo admin: cotizar para el cliente del pedido. */
  clienteId?: number | null;
  /** Solo admin: override del descuento del cliente (el builder lo edita en vivo). */
  descuentoPct?: number | null;
  enabled?: boolean;
}): { data: Cotizacion; isFetching: boolean } {
  const { items, fechaDesde, fechaHasta, clienteId, descuentoPct, enabled = true } = args;

  const body = {
    items: items
      .filter((i) => i.cantidad > 0)
      .map((i) => ({ equipo_id: i.equipoId, cantidad: i.cantidad })),
    fecha_desde: fechaDesde ?? null,
    fecha_hasta: fechaHasta ?? null,
    cliente_id: clienteId ?? null,
    descuento_pct: descuentoPct ?? null,
  };

  const q = useQuery({
    queryKey: ["cotizar", body],
    queryFn: () => authedPostJson<CotizarResp>("/api/cotizar", body),
    enabled: enabled && body.items.length > 0,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

  return {
    data: q.data ? adaptar(q.data) : COTIZACION_VACIA,
    isFetching: q.isFetching,
  };
}

/** Etiqueta de la fila de descuento. Cuando gana el del cliente se personaliza
 *  con su nombre ("Descuento para Tincho") — atención manual del dueño. */
export function descuentoLabel(
  origen: DescuentoOrigen,
  jornadas: number,
  nombreCliente?: string | null,
): string {
  if (origen === "jornadas") {
    return `Descuento jornadas (${jornadas} ${jornadas === 1 ? "jornada" : "jornadas"})`;
  }
  if (origen === "cliente") {
    const nombre = nombreCliente?.trim();
    return nombre ? `Descuento para ${nombre}` : "Descuento cliente";
  }
  return "";
}
