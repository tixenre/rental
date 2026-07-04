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
} | null;

let cached: ClienteSession | undefined; // undefined = no fetched yet
let pending: Promise<ClienteSession> | null = null;
const subscribers = new Set<(s: ClienteSession) => void>();

async function fetchClienteSession(): Promise<ClienteSession> {
  try {
    const r = await authedFetch("/api/cliente/me");
    if (!r.ok) return null;
    const data = await r.json();
    return {
      id: data.id,
      email: data.email,
      nombre: typeof data.nombre === "string" ? data.nombre : null,
      perfil_impuestos: (data.perfil_impuestos ?? null) as PerfilImpuestos | null,
      descuento: typeof data.descuento === "number" ? data.descuento : null,
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
}
