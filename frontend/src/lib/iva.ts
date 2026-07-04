/**
 * iva.ts — Perfil tributario del cliente para el front.
 *
 * El front NO calcula IVA: el monto del IVA lo computa el backend
 * (`services/precios.calcular_total`, vía `/api/cotizar` y el desglose de cada
 * pedido). Acá solo vive `aplicaIva()` — el predicado para decidir si mostrar
 * la leyenda "+ IVA" — y el hook de sesión del cliente. La alícuota (21%) vive
 * únicamente en el backend.
 */

import { useEffect, useState } from "react";
import { authedFetch } from "./authedFetch";
import { queryClient } from "./queryClient";

export type PerfilImpuestos =
  | "consumidor_final"
  | "responsable_inscripto"
  | "monotributo"
  | "exento";

export const PERFIL_IMPUESTOS_LABEL: Record<PerfilImpuestos, string> = {
  consumidor_final: "Consumidor final",
  monotributo: "Monotributo",
  responsable_inscripto: "Resp. inscripto",
  exento: "Exento",
};

export function aplicaIva(perfil: PerfilImpuestos | null | undefined): boolean {
  return perfil === "responsable_inscripto";
}

/** Qué tipo de comprobante espera recibir el cliente, a nivel informativo —
 *  la determinación real (que también depende de la condición del emisor)
 *  la hace `services/facturacion/engine.py::tipo_comprobante` al emitir. */
export function facturaTipoLabel(perfil: PerfilImpuestos | null | undefined): string {
  return aplicaIva(perfil) ? "Factura A" : "Factura B";
}

// ── Hook de sesión cliente (lightweight, una sola llamada compartida) ────

type ClienteSession = {
  id: number;
  email: string;
  /** Nombre de pila del cliente (para personalizar etiquetas en el UI:
   * "Descuento para Tincho", avatar del TopBar, etc.). */
  nombre: string | null;
  perfil_impuestos: PerfilImpuestos | null;
  /** Descuento personalizado del cliente (atención manual del admin a
   * buenos clientes, 0..100). Lo lee el carrito; no es público. */
  descuento: number | null;
  /** Vista de identidad/contacto YA RESUELTA por el backend — mismo criterio
   *  que contrato/remito (RENAPER si está verificado, si no el dato base;
   *  teléfono verificado por Didit si existe, si no el autodeclarado; ver
   *  `identity/__init__.py` + `identity/contacts.py`). El resumen del
   *  checkout ("Tus datos") los muestra tal cual — no reimplementa la regla. */
  nombreLegal: string | null;
  direccionLegal: string | null;
  emailComunicacion: string | null;
  telefonoContacto: string | null;
} | null;

let cached: ClienteSession | undefined; // undefined = no fetched yet
let pending: Promise<ClienteSession> | null = null;
const subscribers = new Set<(s: ClienteSession) => void>();

function _str(v: unknown): string | null {
  return typeof v === "string" ? v : null;
}

async function fetchClienteSession(): Promise<ClienteSession> {
  try {
    const r = await authedFetch("/api/cliente/me");
    if (!r.ok) return null;
    const data = await r.json();
    return {
      id: data.id,
      email: data.email,
      nombre: _str(data.nombre),
      perfil_impuestos: (data.perfil_impuestos ?? null) as PerfilImpuestos | null,
      descuento: typeof data.descuento === "number" ? data.descuento : null,
      nombreLegal: _str(data.nombre_legal),
      direccionLegal: _str(data.direccion_legal),
      emailComunicacion: _str(data.email_comunicacion),
      telefonoContacto: _str(data.telefono_contacto),
    };
  } catch {
    return null;
  }
}

/** Devuelve la sesión del cliente (o null si no logueado). Caché global
 * para no repetir el fetch en cada componente. Se puede invalidar con
 * `invalidateClienteSession()` (ej. después de editar perfil). */
export function useClienteSession(): { data: ClienteSession; loading: boolean } {
  const [data, setData] = useState<ClienteSession>(cached ?? null);
  const [loading, setLoading] = useState(cached === undefined);

  useEffect(() => {
    if (cached !== undefined) {
      setData(cached);
      setLoading(false);
      return;
    }
    let alive = true;
    const sub = (s: ClienteSession) => {
      if (alive) {
        setData(s);
        setLoading(false);
      }
    };
    subscribers.add(sub);
    if (!pending) {
      pending = fetchClienteSession().then((s) => {
        cached = s;
        subscribers.forEach((fn) => fn(s));
        pending = null;
        return s;
      });
    }
    return () => {
      alive = false;
      subscribers.delete(sub);
    };
  }, []);

  return { data, loading };
}

export function invalidateClienteSession() {
  cached = undefined;
  pending = null;
  // El perfil fiscal recién cambió (editar perfil, verificar CUIT con ARCA) —
  // toda cotización en cache puede tener el "+ IVA"/total viejo: `/api/cotizar`
  // resuelve `con_iva` según el perfil ACTUAL del cliente autenticado (no lo
  // manda el front, #617), así que el queryKey de `useCotizacion` (items/fechas)
  // no cambia solo porque el perfil cambió — sin esto, el Total del checkout
  // quedaba stale si el cliente verificaba su CUIT en el mismo modal.
  void queryClient.invalidateQueries({ queryKey: ["cotizar"] });
}
