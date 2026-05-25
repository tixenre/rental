/**
 * iva.ts — Helpers de IVA para mostrar precios al cliente.
 *
 * Asunción: los precios cargados (`precio_jornada` en backend) son NETOS
 * (sin IVA). Para Responsable Inscripto se discrimina IVA = 21%; el resto
 * de perfiles ve el precio tal cual sin sumar IVA (mantiene el
 * comportamiento histórico del catálogo público).
 *
 * Si en el futuro cambia el régimen, ajustar `IVA_RATE` y este archivo.
 */

import { useEffect, useState } from "react";
import { authedFetch } from "./authedFetch";

export const IVA_RATE = 0.21;
export const IVA_PCT = 21;

export type PerfilImpuestos =
  | "consumidor_final"
  | "responsable_inscripto"
  | "monotributo"
  | "exento";

export function aplicaIva(perfil: PerfilImpuestos | null | undefined): boolean {
  return perfil === "responsable_inscripto";
}

/** Descompone un precio neto en {neto, iva, total} según el perfil. Para
 * consumidor final / monotributo / exento, iva = 0 y total = neto. */
export function desglosarIva(
  neto: number,
  perfil: PerfilImpuestos | null | undefined,
): { neto: number; iva: number; total: number } {
  if (!aplicaIva(perfil)) {
    return { neto, iva: 0, total: neto };
  }
  const iva = Math.round(neto * IVA_RATE);
  return { neto, iva, total: neto + iva };
}

// ── Hook de sesión cliente (lightweight, una sola llamada compartida) ────

type ClienteSession = {
  id: number;
  email: string;
  perfil_impuestos: PerfilImpuestos | null;
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
      perfil_impuestos: (data.perfil_impuestos ?? null) as PerfilImpuestos | null,
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
