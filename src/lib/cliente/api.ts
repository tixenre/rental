/**
 * cliente/api.ts — API client del portal de cliente.
 *
 * Reusa los tipos `Pedido`, `PedidoEstado` del admin (es el mismo shape
 * — el cliente sólo ve sus propios pedidos). Los endpoints son
 * /api/cliente/... y validan ownership en el backend.
 */

import { authedFetch, authedJson } from "@/lib/authedFetch";
import type { Pedido } from "@/lib/admin/api";

export type ClientePedidoFull = Pedido & {
  documentos_disponibles?: { remito: boolean; contrato: boolean; albaran: boolean };
  solicitudes?: SolicitudModificacion[];
};

export type SolicitudModificacion = {
  id: number;
  mensaje: string | null;
  estado: "pendiente" | "aprobada" | "rechazada" | "cancelada";
  respuesta: string | null;
  cambios_json?: ModificacionPayload | null;
  tipo?: "directo" | "aprobacion";
  resolved_at?: string | null;
  resolved_by?: string | null;
  created_at: string;
};

export type ModificacionItem = {
  equipo_id: number;
  cantidad: number;
};

export type ModificacionPayload = {
  fecha_desde?: string | null;
  fecha_hasta?: string | null;
  items: ModificacionItem[];
  mensaje?: string | null;
};

export type ModificacionResp =
  | { ok: true; tipo: "directo"; pedido: Pedido }
  | { ok: true; tipo: "aprobacion" };

export const clienteApi = {
  getPedido: (id: number) => authedJson<ClientePedidoFull>(`/api/cliente/pedidos/${id}`),

  modificacionConfig: () =>
    authedJson<{ ventana_horas: number }>("/api/cliente/modificacion-config"),

  /** Aplica un cambio (directo si presupuesto, propuesta si confirmado). */
  enviarModificacion: (id: number, payload: ModificacionPayload) =>
    authedJson<ModificacionResp>(`/api/cliente/pedidos/${id}/modificacion`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  /** Cancela una solicitud pendiente que el propio cliente creó. */
  cancelarSolicitud: async (pedidoId: number, sm_id: number) => {
    const res = await authedFetch(`/api/cliente/pedidos/${pedidoId}/modificacion/${sm_id}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail?.detail ?? `DELETE → ${res.status}`);
    }
  },

  /** Disponibilidad por equipo en un rango, excluyendo el pedido actual. */
  getDisponibilidad: (pedidoId: number, fechaDesde: string, fechaHasta: string) => {
    const sp = new URLSearchParams({ fecha_desde: fechaDesde, fecha_hasta: fechaHasta });
    return authedJson<Record<string, number>>(
      `/api/cliente/pedidos/${pedidoId}/disponibilidad?${sp.toString()}`,
    );
  },
};
