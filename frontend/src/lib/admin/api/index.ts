/**
 * Admin API client — barrel. Re-exports all types + assembles `adminApi`.
 *
 * El path @/lib/admin/api resuelve a este index, por lo que todos los
 * imports existentes (adminApi, tipos, constantes) siguen funcionando sin
 * cambios en los call sites.
 */

export * from "./types";
export { estudioAdminApi } from "./estudio";
export { descuentosJornadaApi } from "./estudio";

// URL absoluta para abrir PDFs en nueva pestaña
const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
export const pedidoPdfUrl = (
  id: number,
  kind: "pdf" | "albaran" | "contrato" | "packing-list" = "pdf",
) => `${API_BASE}/api/alquileres/${id}/${kind}`;

import type { EstadoPedido } from "@/lib/pedido-estados";

export const ESTADO_LABEL: Record<EstadoPedido, string> = {
  borrador: "Borrador",
  presupuesto: "Presupuesto",
  solicitado: "Solicitado",
  confirmado: "Confirmado",
  retirado: "Retirado",
  entregado: "Entregado",
  devuelto: "Devuelto",
  finalizado: "Finalizado",
  cancelado: "Cancelado",
};

import { equiposMethods } from "./equipos";
import { specsMethods } from "./specs";
import { pedidosMethods } from "./pedidos";
import { contabilidadMethods } from "./contabilidad";
import { brandingMethods } from "./branding";

export const adminApi = {
  ...equiposMethods,
  ...specsMethods,
  ...pedidosMethods,
  ...contabilidadMethods,
  ...brandingMethods,
};
