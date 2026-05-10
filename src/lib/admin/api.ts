/**
 * Admin API client — wrappers tipados de los endpoints del back-office FastAPI.
 *
 * Todos requieren JWT de Supabase con email en ADMIN_EMAILS (validado por
 * `require_admin` en backend/supabase_auth.py), salvo cuando el backend
 * tiene ADMIN_BYPASS_AUTH=1.
 */

import { authedFetch, authedJson, authedPostJson } from "@/lib/authedFetch";

// ── Dashboard ────────────────────────────────────────────────────────────

export type DashboardData = {
  pendientes: number;
  activos: number;
  ingresos_mes: number;
  total_clientes: number;
  salen_hoy: PedidoResumen[];
  devuelven_hoy: PedidoResumen[];
  devuelven_manana: PedidoResumen[];
  equipos_afuera: EquipoAfuera[];
};

export type PedidoResumen = {
  id: number;
  cliente_nombre: string;
  fecha_desde: string;
  fecha_hasta: string;
  monto_total: number;
};

export type EquipoAfuera = {
  nombre: string;
  marca: string | null;
  cantidad: number;
  cliente_nombre: string;
  fecha_hasta: string;
};

// ── Equipos ──────────────────────────────────────────────────────────────

export type Equipo = {
  id: number;
  nombre: string;
  marca: string | null;
  modelo: string | null;
  cantidad: number;
  precio_jornada: number | null;
  precio_usd: number | null;
  roi_pct: number | null;
  valor_reposicion: number | null;
  foto_url: string | null;
  fecha_compra: string | null;
  serie: string | null;
  bh_url: string | null;
  dueno: string | null;
  visible_catalogo: number;
  estado: string;
  etiquetas?: string[];
};

export type EquiposListResp = {
  total: number;
  page: number;
  per_page: number;
  items: Equipo[];
};

export type EquipoInput = Partial<Omit<Equipo, "id" | "etiquetas">> & {
  nombre: string;
};

export type Etiqueta = { id: number; nombre: string; uso_count?: number };

export const adminApi = {
  dashboard: () => authedJson<DashboardData>("/api/dashboard"),

  // equipos
  listEquipos: (params: { q?: string; etiqueta?: string; per_page?: number } = {}) => {
    const sp = new URLSearchParams();
    if (params.q) sp.set("q", params.q);
    if (params.etiqueta) sp.set("etiqueta", params.etiqueta);
    sp.set("per_page", String(params.per_page ?? 500));
    return authedJson<EquiposListResp>(`/api/equipos?${sp.toString()}`);
  },
  getEquipo: (id: number) => authedJson<Equipo & { kit: unknown[] }>(`/api/equipos/${id}`),
  createEquipo: (data: EquipoInput) =>
    authedPostJson<Equipo>("/api/equipos", data),
  updateEquipo: (id: number, data: Partial<EquipoInput>) =>
    authedJson<Equipo>(`/api/equipos/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deleteEquipo: async (id: number) => {
    const res = await authedFetch(`/api/equipos/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail?.detail ?? `DELETE → ${res.status}`);
    }
  },
  setEtiquetas: (id: number, etiquetas: string[]) =>
    authedJson<{ ok: true }>(`/api/equipos/${id}/etiquetas`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ etiquetas }),
    }),
  listEtiquetas: () => authedJson<Etiqueta[]>("/api/etiquetas"),
};
