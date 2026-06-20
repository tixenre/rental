import { authedFetch, authedJson, authedPostJson } from "@/lib/authedFetch";
import type {
  DashboardData,
  DashboardUso,
  EquiposListResp,
  FaltaField,
  Equipo,
  CalidadInventario,
  SugerenciasResp,
  Sugerencia,
  EquipoInput,
  MantenimientoEvento,
  MantenimientoInput,
  Etiqueta,
  KitComponente,
  Ficha,
  Categoria,
  CategoriaAdmin,
  EtiquetaAdmin,
  MarcaAdmin,
  ClasificarResult,
} from "./types";

export const equiposMethods = {
  dashboard: () => authedJson<DashboardData>("/api/dashboard"),
  dashboardUso: (dias_sin_uso = 90) =>
    authedJson<DashboardUso>(`/api/admin/dashboard/uso?dias_sin_uso=${dias_sin_uso}`),

  // equipos
  listEquipos: (
    params: {
      q?: string;
      etiqueta?: string;
      categoria?: string;
      marca?: string;
      per_page?: number;
      solo_incompletos?: boolean;
      solo_eliminados?: boolean;
      incluir_eliminados?: boolean;
      falta?: FaltaField;
    } = {},
  ) => {
    const sp = new URLSearchParams();
    if (params.q) sp.set("q", params.q);
    if (params.etiqueta) sp.set("etiqueta", params.etiqueta);
    if (params.categoria) sp.set("categoria", params.categoria);
    if (params.marca) sp.set("marca", params.marca);
    if (params.solo_incompletos) sp.set("solo_incompletos", "true");
    if (params.solo_eliminados) sp.set("solo_eliminados", "true");
    if (params.incluir_eliminados) sp.set("incluir_eliminados", "true");
    if (params.falta) sp.set("falta", params.falta);
    sp.set("per_page", String(params.per_page ?? 500));
    return authedJson<EquiposListResp>(`/api/equipos?${sp.toString()}`);
  },
  /** KPIs del inventario para el header de /admin/equipos. */
  equiposKpis: () =>
    authedJson<{ total: number; en_uso_hoy: number; mantenimiento: number }>("/api/equipos/kpis"),
  restoreEquipo: (id: number) =>
    authedPostJson<{ ok: true; message?: string }>(`/api/equipos/${id}/restore`, {}),
  getEquipo: (id: number) => authedJson<Equipo>(`/api/equipos/${id}`),
  /** Calidad del inventario — métricas + breakdown por campo faltante. Issue #349. */
  getCalidadInventario: () => authedJson<CalidadInventario>("/api/admin/inventario/calidad"),
  /** Sugerencias automáticas para mejorar el inventario. Issue #352. */
  getSugerenciasInventario: () => authedJson<SugerenciasResp>("/api/admin/inventario/sugerencias"),
  aplicarSugerencia: (tipo: Sugerencia["tipo"], ref: string) =>
    authedPostJson<{ ok: true; message: string }>("/api/admin/inventario/sugerencias/aplicar", {
      tipo,
      ref,
    }),
  ignorarSugerencia: (tipo: Sugerencia["tipo"], ref: string) =>
    authedPostJson<{ ok: true; message: string }>("/api/admin/inventario/sugerencias/ignorar", {
      tipo,
      ref,
    }),
  /** Equipos sin número de serie cargado (NULL o vacío). Issue #91. */
  getEquiposSinSerie: () =>
    authedJson<{
      total: number;
      equipos: Array<{
        id: number;
        nombre: string;
        marca: string | null;
        modelo: string | null;
        foto_url: string | null;
        valor_reposicion: number | null;
        dueno: string | null;
        cantidad: number;
      }>;
    }>("/api/admin/equipos/sin-serie"),
  createEquipo: (data: EquipoInput) => authedPostJson<Equipo>("/api/equipos", data),
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
  duplicateEquipo: (id: number) =>
    authedJson<Equipo>(`/api/equipos/${id}/duplicate`, { method: "POST" }),
  /** Bulk action sobre múltiples equipos. */
  bulkAction: (payload: {
    ids: number[];
    action:
      | "set_visible"
      | "set_ficha_completa"
      | "set_categoria"
      | "add_categoria"
      | "remove_categoria"
      | "delete"
      | "delete_permanent";
    visible?: boolean;
    ficha_completa?: boolean;
    categoria_id?: number;
  }) => authedPostJson<{ affected: number }>("/api/admin/equipos/bulk", payload),
  // Mantenimiento log por equipo
  listMantenimiento: (equipoId: number) =>
    authedJson<{
      items: MantenimientoEvento[];
      stats: { total_eventos: number; total_costo: number; proxima_revision: string | null };
    }>(`/api/equipos/${equipoId}/mantenimiento`),
  addMantenimiento: (equipoId: number, data: MantenimientoInput) =>
    authedPostJson<MantenimientoEvento>(`/api/equipos/${equipoId}/mantenimiento`, data),
  updateMantenimiento: (equipoId: number, logId: number, data: Partial<MantenimientoInput>) =>
    authedJson<MantenimientoEvento>(`/api/equipos/${equipoId}/mantenimiento/${logId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deleteMantenimiento: async (equipoId: number, logId: number) => {
    const res = await authedFetch(`/api/equipos/${equipoId}/mantenimiento/${logId}`, {
      method: "DELETE",
    });
    if (!res.ok && res.status !== 204) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail?.detail ?? `DELETE → ${res.status}`);
    }
  },
  getEquipoHistorial: (id: number) =>
    authedJson<{
      historial: Array<{
        id: number;
        numero_pedido: string;
        estado: string;
        fecha_desde: string;
        fecha_hasta: string;
        cliente: string;
        cantidad: number;
        precio_item: number;
        dias: number;
      }>;
      stats: {
        total_alquileres: number;
        total_dias: number;
        total_revenue: number;
        ultimo_alquiler: string | null;
      };
    }>(`/api/equipos/${id}/historial`),
  setEtiquetas: (id: number, etiquetas: string[]) =>
    authedJson<{ ok: true }>(`/api/equipos/${id}/etiquetas`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ etiquetas }),
    }),
  setCategorias: (id: number, categoria_ids: number[]) =>
    authedJson<{ ok: true }>(`/api/equipos/${id}/categorias`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ categoria_ids }),
    }),

  // ficha técnica
  getFicha: (id: number) => authedJson<Ficha & { equipo_id?: number }>(`/api/equipos/${id}/ficha`),
  setFicha: (id: number, data: Partial<Ficha>) =>
    authedJson<Ficha>(`/api/equipos/${id}/ficha`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  // kit / componentes
  getKit: (id: number) => authedJson<KitComponente[]>(`/api/equipos/${id}/kit`),
  addKitItem: (
    id: number,
    componente_id: number,
    cantidad = 1,
    descuento_pct?: number | null,
    esencial?: boolean,
  ) =>
    authedPostJson<KitComponente[]>(`/api/equipos/${id}/kit`, {
      componente_id,
      cantidad,
      descuento_pct: descuento_pct ?? 0,
      esencial: esencial ?? true,
    }),
  removeKitItem: async (id: number, componente_id: number) => {
    const res = await authedFetch(`/api/equipos/${id}/kit/${componente_id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail?.detail ?? `DELETE → ${res.status}`);
    }
  },
  reorderKit: (id: number, orden: number[]) =>
    authedPostJson<{ ok: boolean }>(`/api/admin/equipos/${id}/kit/reorder`, { orden }),
  listEtiquetas: (incluirAuto = false) =>
    authedJson<Etiqueta[]>(`/api/etiquetas${incluirAuto ? "?incluir_auto=1" : ""}`),

  // categorías (público — árbol con totales)
  listCategorias: () => authedJson<Categoria[]>("/api/categorias"),

  // categorías (admin)
  adminListCategorias: () => authedJson<CategoriaAdmin[]>("/api/admin/categorias"),
  adminCreateCategoria: (data: { nombre: string; prioridad?: number; parent_id?: number | null }) =>
    authedPostJson<CategoriaAdmin>("/api/admin/categorias", data),
  adminUpdateCategoria: (
    id: number,
    patch: {
      nombre?: string;
      prioridad?: number;
      parent_id?: number | null;
      set_parent_null?: boolean;
      visible?: boolean;
      nombre_publico_template?: string | null;
    },
  ) =>
    authedJson<{ ok: true }>(`/api/admin/categorias/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),
  adminDeleteCategoria: async (id: number) => {
    const res = await authedFetch(`/api/admin/categorias/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail?.detail ?? `DELETE → ${res.status}`);
    }
  },
  adminReorderCategorias: (ids: number[]) =>
    authedPostJson<{ ok: true; count: number }>("/api/admin/categorias/reorder", { ids }),

  // etiquetas (admin) — bolsa libre
  adminListEtiquetas: () => authedJson<EtiquetaAdmin[]>("/api/admin/etiquetas"),
  adminCreateEtiqueta: (data: { nombre: string; prioridad?: number; parent_id?: number | null }) =>
    authedPostJson<EtiquetaAdmin>("/api/admin/etiquetas", data),
  adminUpdateEtiqueta: (
    id: number,
    patch: {
      nombre?: string;
      prioridad?: number;
      parent_id?: number | null;
      set_parent_null?: boolean;
    },
  ) =>
    authedJson<{ ok: true }>(`/api/admin/etiquetas/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),
  adminDeleteEtiqueta: async (id: number) => {
    const res = await authedFetch(`/api/admin/etiquetas/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail?.detail ?? `DELETE → ${res.status}`);
    }
  },
  adminReorderEtiquetas: (ids: number[]) =>
    authedPostJson<{ ok: true; count: number }>("/api/admin/etiquetas/reorder", { ids }),

  // marcas (admin)
  adminListMarcas: () => authedJson<{ items: MarcaAdmin[] }>("/api/admin/marcas"),
  adminUpdateMarca: (id: number, patch: Partial<MarcaAdmin>) =>
    authedJson<MarcaAdmin>(`/api/admin/marcas/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),
  adminReorderMarcas: (reorder: { id: number; orden: number }[]) =>
    authedPostJson<{ ok: true }>("/api/admin/marcas/reorder", { marcas: reorder }),
  adminMergeMarcas: (sourceId: number, targetId: number) =>
    authedPostJson<{ ok: boolean; merged_into: string }>("/api/admin/marcas/merge", {
      source_id: sourceId,
      target_id: targetId,
    }),
  adminDeleteMarca: (id: number) =>
    authedJson<void>(`/api/admin/marcas/${id}`, { method: "DELETE" }),
  adminUploadMarcaLogo: async (id: number, file: File): Promise<string> => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await authedFetch(`/api/admin/marcas/${id}/upload-logo`, {
      method: "POST",
      body: fd,
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail?.detail ?? `upload-logo → ${res.status}`);
    }
    const data = (await res.json()) as { public_url: string };
    return data.public_url;
  },

  adminClasificarDryRun: () =>
    authedPostJson<ClasificarResult>("/api/admin/categorias/clasificar?apply=0", {}),
  adminClasificarApply: () =>
    authedPostJson<ClasificarResult>("/api/admin/categorias/clasificar?apply=1", {}),
};
