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

  // pedidos / alquileres
  listPedidos: (params: { estado?: string; q?: string; per_page?: number; page?: number } = {}) => {
    const sp = new URLSearchParams();
    if (params.estado) sp.set("estado", params.estado);
    if (params.q) sp.set("q", params.q);
    sp.set("per_page", String(params.per_page ?? 100));
    sp.set("page", String(params.page ?? 1));
    return authedJson<PedidosListResp>(`/api/alquileres?${sp.toString()}`);
  },
  getPedido: (id: number) => authedJson<Pedido>(`/api/alquileres/${id}`),
  setPedidoEstado: (id: number, estado: PedidoEstado) =>
    authedJson<Pedido>(`/api/alquileres/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ estado }),
    }),
  updatePedidoDatos: (id: number, data: Partial<PedidoDatosInput>) =>
    authedJson<Pedido>(`/api/alquileres/${id}/datos`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deletePedido: async (id: number) => {
    const res = await authedFetch(`/api/alquileres/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail?.detail ?? `DELETE → ${res.status}`);
    }
  },
  addPago: (id: number, monto: number, concepto?: string, fecha?: string) =>
    authedPostJson<Pedido>(`/api/alquileres/${id}/pagos`, { monto, concepto, fecha }),
  deletePago: async (id: number, pagoId: number) => {
    const res = await authedFetch(`/api/alquileres/${id}/pagos/${pagoId}`, { method: "DELETE" });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail?.detail ?? `DELETE → ${res.status}`);
    }
    return res.json();
  },

  // clientes
  listClientes: (params: { q?: string; per_page?: number } = {}) => {
    const sp = new URLSearchParams();
    if (params.q) sp.set("q", params.q);
    sp.set("per_page", String(params.per_page ?? 200));
    return authedJson<ClientesListResp>(`/api/clientes?${sp.toString()}`);
  },
  createCliente: (data: ClienteInput) => authedPostJson<Cliente>("/api/clientes", data),

  // disponibilidad por rango (mapa equipo_id → { cantidad, reservado })
  getDisponibilidad: (
    fechaDesde: string,
    fechaHasta: string,
    excludePedidoId?: number,
  ) => {
    const sp = new URLSearchParams({ fecha_desde: fechaDesde, fecha_hasta: fechaHasta });
    if (excludePedidoId) sp.set("exclude_pedido_id", String(excludePedidoId));
    return authedJson<Record<string, { cantidad: number; reservado: number }>>(
      `/api/disponibilidad?${sp.toString()}`,
    );
  },

  // crear pedido nuevo (wizard)
  createPedido: (data: PedidoCreateInput) => authedPostJson<Pedido>("/api/alquileres", data),
};

export type Cliente = {
  id: number;
  nombre: string;
  apellido: string;
  telefono: string | null;
  email: string | null;
  direccion: string | null;
  cuit: string | null;
  descuento: number | null;
  perfil_impuestos: string | null;
};
export type ClientesListResp = {
  total: number; page: number; per_page: number; items: Cliente[];
};
export type ClienteInput = {
  nombre: string;
  apellido: string;
  telefono?: string;
  email?: string;
  direccion?: string;
  cuit?: string;
  descuento?: number;
  perfil_impuestos?: string;
};

export type PedidoCreateInput = {
  cliente_id?: number | null;
  cliente_nombre?: string;
  cliente_email?: string | null;
  cliente_telefono?: string | null;
  notas?: string | null;
  fecha_desde?: string | null;
  fecha_hasta?: string | null;
  items: { equipo_id: number; cantidad: number; precio_jornada: number }[];
  estado?: "borrador" | "presupuesto";
};

// ── Tipos pedidos ────────────────────────────────────────────────────────

export type PedidoEstado =
  | "borrador" | "presupuesto" | "confirmado" | "retirado"
  | "devuelto" | "finalizado" | "cancelado";

export type PedidoItem = {
  id: number;
  pedido_id: number;
  equipo_id: number;
  cantidad: number;
  precio_jornada: number;
  subtotal: number;
  nombre: string;
  marca: string | null;
};

export type PedidoPago = {
  id: number;
  pedido_id: number;
  monto: number;
  concepto: string | null;
  fecha: string;
  created_at?: string;
};

export type Pedido = {
  id: number;
  numero_pedido: number | null;
  numero_remito: string | null;
  cliente_id: number | null;
  cliente_nombre: string | null;
  cliente_email: string | null;
  cliente_telefono: string | null;
  fecha_desde: string | null;
  fecha_hasta: string | null;
  estado: PedidoEstado;
  fuente: string | null;
  monto_total: number;
  monto_pagado: number;
  descuento_pct: number | null;
  notas: string | null;
  created_at?: string;
  items: PedidoItem[];
  pagos?: PedidoPago[];
};

export type PedidosListResp = {
  total: number;
  page: number;
  per_page: number;
  items: Pedido[];
};

export type PedidoDatosInput = {
  cliente_id: number | null;
  cliente_nombre: string | null;
  cliente_email: string | null;
  cliente_telefono: string | null;
  fecha_desde: string | null;
  fecha_hasta: string | null;
  notas: string | null;
  descuento_pct: number | null;
};

// URL absoluta para abrir PDFs en nueva pestaña (FastAPI sirve directo).
const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
export const pedidoPdfUrl = (id: number, kind: "pdf" | "albaran" | "contrato" = "pdf") =>
  `${API_BASE}/api/alquileres/${id}/${kind}`;

export const ESTADO_LABEL: Record<PedidoEstado, string> = {
  borrador: "Borrador",
  presupuesto: "Presupuesto",
  confirmado: "Confirmado",
  retirado: "Retirado",
  devuelto: "Devuelto",
  finalizado: "Finalizado",
  cancelado: "Cancelado",
};

