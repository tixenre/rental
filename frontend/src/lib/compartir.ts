/**
 * Cliente del link "compartir composición" (#1092 feature #4 — gaffer → productor).
 *
 * Crea / lee un carrito compartido por la puerta PÚBLICA `/api/public/compartir`
 * (sin login — el destinatario puede no tener cuenta). Reusa `authedJson` /
 * `authedPostJson`: mandan la cookie `session` con `credentials: "include"`, así
 * que si quien comparte está logueado el backend captura su `cliente_id` como
 * atribución (inofensivo si es anónimo). El destinatario rearma la composición
 * en SU carrito con la primitiva única `rearmarCarrito` (re-cotiza contra el
 * catálogo actual — NO el snapshot congelado, MEMORIA 2026-06-06).
 */
import { authedJson, authedPostJson } from "@/lib/authedFetch";

/** Una línea de la composición tal como viaja a/desde el backend. */
export type CompartirItem = { equipo_id: number; cantidad: number };

export type CompartidoCreado = { token: string; url: string };

export type CompartidoData = {
  token: string;
  titulo: string | null;
  items: CompartirItem[];
  created_at: string;
};

/** Crea un link compartible para una composición. `titulo` es opcional. */
export async function crearCompartido(
  items: CompartirItem[],
  titulo?: string | null,
): Promise<CompartidoCreado> {
  return authedPostJson<CompartidoCreado>("/api/public/compartir", {
    titulo: titulo?.trim() || null,
    items,
  });
}

/** Trae la composición de un link compartido. Token inválido → AuthedHttpError 404. */
export async function getCompartido(token: string): Promise<CompartidoData> {
  return authedJson<CompartidoData>(`/api/public/compartir/${encodeURIComponent(token)}`);
}
