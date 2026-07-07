import { authedFetch, authedJson } from "@/lib/authedFetch";
import type { CambiosJson, PedidoLite, Solicitud } from "./types";

export const solicitudesAdminApi = {
  list: () => authedJson<Solicitud[]>("/api/admin/solicitudes"),

  resolver: async (args: {
    id: number;
    estado: "aprobada" | "rechazada";
    respuesta: string;
    cambios_override?: CambiosJson;
  }) => {
    const body: Record<string, unknown> = {
      estado: args.estado,
      respuesta: args.respuesta,
    };
    if (args.cambios_override) body.cambios_override = args.cambios_override;
    const res = await authedFetch(`/api/admin/solicitudes/${args.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail?.detail ?? `PATCH → ${res.status}`);
    }
  },

  getPedido: (pedidoId: number) => authedJson<PedidoLite>(`/api/alquileres/${pedidoId}`),
};
