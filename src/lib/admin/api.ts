/**
 * Admin API client — wrappers tipados de los endpoints del back-office FastAPI.
 *
 * Todos requieren JWT de Supabase con email en ADMIN_EMAILS (validado por
 * `require_admin` en backend/supabase_auth.py), salvo cuando el backend
 * tiene ADMIN_BYPASS_AUTH=1.
 */

import { authedFetch, authedJson, authedPostJson } from "@/lib/authedFetch";

// ── Dashboard ────────────────────────────────────────────────────────────

/** Campos que el dashboard de calidad sabe detectar como faltantes (#349, #350). */
export type FaltaField =
  | "foto"
  | "categoria"
  | "nombre_publico"
  | "descripcion"
  | "serie"
  | "valor_reposicion";

/** Sugerencia automática del sistema (#352). */
export type Sugerencia = {
  tipo: "marcas_duplicadas" | "precio_sin_usd" | "categoria_sospechosa";
  ref: string;
  titulo: string;
  detalle: string;
  accion: "fusionar" | "calcular_usd" | "asignar_categoria" | string;
  accion_label: string;
  // Payloads específicos por tipo.
  marcas?: Array<{ id: number; nombre: string; cant_pedidos: number; equipos: number }>;
  equipos?: Array<{ id: number; nombre: string; marca: string | null; precio_jornada: number }>;
  equipo_id?: number;
  categoria_sugerida?: string;
};

export type SugerenciasResp = {
  items: Sugerencia[];
  total: number;
};

export type CalidadInventario = {
  total: number;
  completos_pct: number;
  faltantes: {
    serie: number;
    valor_reposicion: number;
    foto: number;
    descripcion: number;
    nombre_publico: number;
    categoria: number;
  };
};

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

export type Ficha = {
  descripcion:   string | null;
  notas:         string | null;
  specs_json:    string | null;
  montura:       string | null;
  formato:       string | null;
  resolucion:    string | null;
  keywords_json: string | null;
  nombre_publico_template?: string | null;
  // Ficha extendida (enriquecimiento)
  peso?:                string | null;
  dimensiones?:         string | null;
  alimentacion?:        string | null;
  incluye_json?:        string | null;
  conectividad_json?:   string | null;
  compatible_con_json?: string | null;
  video_url?:           string | null;
  precio_bh_usd?:       number | null;
  fuente_url?:          string | null;
  fuente_titulo?:       string | null;
  enriquecido_at?:      string | null;
  enriquecido_fuente?:  string | null;
  /** Scrape raw cacheado del autocompletar. Lo usa el form para re-aplicar
   *  campos por sección sin volver a scrapear. */
  raw_json?:            string | null;
};

export type CategoriaRef = {
  id: number;
  nombre: string;
  parent_id: number | null;
};

export type Equipo = {
  id: number;
  nombre: string;
  marca: string | null;
  modelo: string | null;
  cantidad: number;
  precio_jornada: number | null;
  /** True si el admin editó el precio a mano (no viene de la fórmula).
   *  El recálculo masivo en modo "auto" respeta estos precios. */
  precio_jornada_manual?: boolean;
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
  /** Flag manual del admin: ficha cargada y revisada (no requiere más trabajo). */
  ficha_completa?: boolean;
  /** Timestamp ISO si el equipo está soft-deleted. null = activo (#206). */
  eliminado_at?: string | null;
  etiquetas?: string[];
  kit?: KitComponente[];
  categorias?: CategoriaRef[];
  ficha?: Ficha;
  /** Nombre público corto (catálogo / cards). Lo arma el backend a partir de specs. */
  nombre_publico?: string | null;
  /** Nombre público extendido (PDFs formales: albarán, contrato). */
  nombre_publico_largo?: string | null;
  /** Relevancia manual (1=más destacado, 100=neutro). */
  relevancia_manual?: number;
  /** Score de popularidad (0..100, normalizado por categoría). */
  popularidad_score?: number;
};

export type KitComponente = {
  componente_id: number;
  cantidad: number;
  orden: number;
  nombre: string;
  marca?: string | null;
  foto_url?: string | null;
};

export type EquiposListResp = {
  total: number;
  page: number;
  per_page: number;
  items: Equipo[];
};

export type EquipoInput = Partial<Omit<Equipo, "id" | "etiquetas" | "kit" | "categorias" | "ficha">> & {
  nombre: string;
};

export type Etiqueta = { nombre: string; total?: number };

export type EtiquetaAdmin = {
  id: number;
  nombre: string;
  prioridad: number;
  parent_id: number | null;
  total: number;
};

// Categoría: vive en su propia taxonomía (tabla `categorias`).
export type CategoriaAdmin = {
  id: number;
  nombre: string;
  prioridad: number;
  parent_id: number | null;
  /** Si false, la categoría no se muestra en el catálogo público. */
  visible: boolean;
  /** Plantilla para generar nombre público de equipos en esta categoría.
   *  Sintaxis: {marca} {modelo} {tipo} {spec:Label}. NULL = sin template. */
  nombre_publico_template?: string | null;
  total: number;
};

// Árbol público para filtros del catálogo.
export type Categoria = {
  id?: number;
  nombre: string;
  total: number;
  prioridad: number;
  parent_id?: number | null;
  children?: Categoria[];
  // legacy flat
  subtags?: { nombre: string; total: number }[];
};

export type ClasificarItem = {
  id: number;
  nombre: string;
  marca: string | null;
  propuestas: string[];
  actuales: string[];
};

export type ClasificarResult = {
  total: number;
  matched: number;
  unmatched: number;
  applied: number;
  items: ClasificarItem[];
};

// ── Mantenimiento por equipo ─────────────────────────────────────────────

export type MantenimientoEvento = {
  id: number;
  equipo_id: number;
  fecha: string;
  tipo: string; // revision / reparacion / limpieza / otro
  descripcion: string | null;
  costo: number | null;
  proxima_revision: string | null;
  created_at?: string;
};

export type MantenimientoInput = {
  fecha: string;
  tipo?: string;
  descripcion?: string | null;
  costo?: number | null;
  proxima_revision?: string | null;
};

export type MarcaAdmin = {
  id: number;
  nombre: string;
  logo_url?: string | null;
  visible: boolean;
  /** Flag para destacar en el BrandCarousel del home. #288 */
  destacada: boolean;
  orden: number;
  total: number;
};

// ── Templates de specs por categoría (CRUD admin) ────────────────────────

export type SpecTipo = "string" | "number" | "enum" | "bool" | "rango";

export type SpecTemplate = {
  id: number;
  categoria_id: number;
  spec_key: string;
  label: string;
  tipo: SpecTipo;
  unidad: string | null;
  enum_options: string[] | null;
  prioridad: number;
  visible_en_card: boolean;
  visible_en_filtros: boolean;
  visible_en_nombre: boolean;
  obligatorio: boolean;
  ayuda: string | null;
  destacado: boolean;
};

export type SpecTemplateInput = {
  spec_key: string;
  label: string;
  tipo: SpecTipo;
  unidad?: string | null;
  enum_options?: string[] | null;
  prioridad?: number;
  visible_en_card?: boolean;
  visible_en_filtros?: boolean;
  visible_en_nombre?: boolean;
  obligatorio?: boolean;
  ayuda?: string | null;
  destacado?: boolean;
};

// Dashboard de uso (#205)
export type DashboardUsoEquipo = {
  id: number;
  nombre: string;
  marca: string | null;
  modelo: string | null;
  foto_url: string | null;
  cant_pedidos: number;
  revenue_total: number | null;
};

export type DashboardUsoSinUso = {
  id: number;
  nombre: string;
  marca: string | null;
  modelo: string | null;
  foto_url: string | null;
  valor_reposicion: number | null;
  ultimo_alquiler: string | null;
  total_alquileres: number;
};

export type DashboardUsoCategoria = {
  id: number;
  nombre: string;
  cant_pedidos: number;
  revenue_total: number | null;
};

export type DashboardUsoPorCobrarItem = {
  id: number;
  numero_pedido: string | number | null;
  estado: string;
  cliente: string;
  fecha_desde: string;
  fecha_hasta: string;
  monto_total: number;
  monto_pagado: number;
  pendiente: number;
};

export type DashboardUso = {
  totales: {
    total_equipos: number;
    total_visibles: number;
    total_pedidos: number;
    revenue_total: number | null;
  };
  top_alquilados: DashboardUsoEquipo[];
  sin_uso: DashboardUsoSinUso[];
  por_categoria: DashboardUsoCategoria[];
  por_cobrar: {
    total: number;
    count: number;
    items: DashboardUsoPorCobrarItem[];
  };
  dias_sin_uso_threshold: number;
};

export type OrphanSpec = {
  spec_key: string;
  count_equipos: number;
  sample_values: string[];
};

export const adminApi = {
  dashboard: () => authedJson<DashboardData>("/api/dashboard"),
  dashboardUso: (dias_sin_uso = 90) =>
    authedJson<DashboardUso>(`/api/admin/dashboard/uso?dias_sin_uso=${dias_sin_uso}`),

  // equipos
  listEquipos: (params: {
    q?: string;
    etiqueta?: string;
    categoria?: string;
    marca?: string;
    per_page?: number;
    solo_incompletos?: boolean;
    solo_eliminados?: boolean;
    incluir_eliminados?: boolean;
    falta?: FaltaField;
  } = {}) => {
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
  restoreEquipo: (id: number) =>
    authedPostJson<{ ok: true; message?: string }>(`/api/equipos/${id}/restore`, {}),
  getEquipo: (id: number) => authedJson<Equipo>(`/api/equipos/${id}`),
  /** Calidad del inventario — métricas + breakdown por campo faltante. Issue #349. */
  getCalidadInventario: () =>
    authedJson<CalidadInventario>("/api/admin/inventario/calidad"),
  /** Sugerencias automáticas para mejorar el inventario. Issue #352. */
  getSugerenciasInventario: () =>
    authedJson<SugerenciasResp>("/api/admin/inventario/sugerencias"),
  aplicarSugerencia: (tipo: Sugerencia["tipo"], ref: string) =>
    authedPostJson<{ ok: true; message: string }>(
      "/api/admin/inventario/sugerencias/aplicar",
      { tipo, ref },
    ),
  ignorarSugerencia: (tipo: Sugerencia["tipo"], ref: string) =>
    authedPostJson<{ ok: true; message: string }>(
      "/api/admin/inventario/sugerencias/ignorar",
      { tipo, ref },
    ),
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
  duplicateEquipo: (id: number) =>
    authedJson<Equipo>(`/api/equipos/${id}/duplicate`, { method: "POST" }),
  /** Bulk action sobre múltiples equipos. */
  bulkAction: (payload: {
    ids: number[];
    action: "set_visible" | "set_ficha_completa" | "set_categoria" | "add_categoria" | "remove_categoria" | "delete" | "delete_permanent";
    visible?: boolean;
    ficha_completa?: boolean;
    categoria_id?: number;
  }) =>
    authedPostJson<{ affected: number }>("/api/admin/equipos/bulk", payload),
  /** Batch autocompletar: procesa hasta 3 equipos por call, guarda el scrape
   *  en cache (raw_json). El frontend re-batchea hasta terminar. */
  batchEnriquecer: (equipo_ids: number[]) =>
    authedPostJson<{
      results: Array<{
        equipo_id: number;
        status: "ok" | "skipped" | "error";
        reason?: string;
        error?: string;
        specs_count?: number;
        filled?: string[];
      }>;
    }>("/api/admin/equipos/batch-enriquecer", { equipo_ids }),
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
    const res = await authedFetch(`/api/equipos/${equipoId}/mantenimiento/${logId}`, { method: "DELETE" });
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
  /** Aplica el resultado de /admin/equipos/autocompletar en un único call.
   *  Acepta cualquier subset de campos; los no enviados quedan como están. */
  aplicarEnriquecimiento: (id: number, data: Record<string, unknown>) =>
    authedJson<{ equipo: Equipo; ficha: Ficha | null }>(
      `/api/admin/equipos/${id}/aplicar-autocompletado`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      },
    ),

  // kit / componentes
  getKit: (id: number) =>
    authedJson<KitComponente[]>(`/api/equipos/${id}/kit`),
  addKitItem: (id: number, componente_id: number, cantidad = 1) =>
    authedPostJson<KitComponente[]>(`/api/equipos/${id}/kit`, {
      componente_id, cantidad,
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
    patch: { nombre?: string; prioridad?: number; parent_id?: number | null; set_parent_null?: boolean },
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
  adminListMarcas: () =>
    authedJson<{ items: MarcaAdmin[] }>("/api/admin/marcas"),
  adminUpdateMarca: (id: number, patch: Partial<MarcaAdmin>) =>
    authedJson<MarcaAdmin>(`/api/admin/marcas/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),
  adminReorderMarcas: (reorder: { id: number; orden: number }[]) =>
    authedPostJson<{ ok: true }>("/api/admin/marcas/reorder", { marcas: reorder }),
  adminMergeMarcas: (sourceId: number, targetId: number) =>
    authedPostJson<{ ok: boolean; merged_into: string }>(
      "/api/admin/marcas/merge",
      { source_id: sourceId, target_id: targetId },
    ),
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

  // ── App settings (key/value globales) ─────────────────────────────────
  getSetting: (key: string) =>
    authedJson<{ key: string; value: string; updated_at: string | null; updated_by: string | null }>(
      `/api/settings/${encodeURIComponent(key)}`,
    ),
  listSettings: () =>
    authedJson<{ items: Array<{ key: string; value: string; updated_at: string | null; updated_by: string | null }> }>(
      "/api/settings",
    ),
  updateSetting: (key: string, value: string | number) =>
    authedJson<{ key: string; value: string; updated_by: string }>(
      `/api/admin/settings/${encodeURIComponent(key)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: String(value) }),
      },
    ),
  /** Modos: "missing" (sin precio), "auto" (respeta manuales — default),
   *  "all" (todos), "ids" (solo los listados). */
  recalcularPrecios: (
    args: { dry_run: boolean; mode?: "missing" | "auto" | "all" | "ids"; ids?: number[] },
  ) =>
    authedPostJson<{
      usd_rate: number; mode: string;
      total_evaluados: number; total_cambios: number;
      cambios: Array<{
        id: number; nombre: string;
        antes: number | null; despues: number;
        delta: number; manual: boolean;
      }>;
      dry_run: boolean;
    }>("/api/admin/settings/recalcular-precios", args),
  /** Lista equipos con precio manual + lo que daría la fórmula con el
   *  USD rate actual. Útil para revisión equipo-por-equipo. */
  listarPreciosManuales: () =>
    authedJson<{
      usd_rate: number;
      items: Array<{
        id: number; nombre: string; marca: string | null; modelo: string | null;
        foto_url: string | null;
        precio_actual: number | null; precio_usd: number | null;
        roi_pct: number | null; precio_calculado: number | null;
        delta: number | null;
      }>;
    }>("/api/admin/equipos/precios-manuales"),

  // ── Clasificación (PR C) ───────────────────────────────────────────
  clasificarBulk: (args: { solo_sin_categoria?: boolean; equipo_ids?: number[] } = {}) =>
    authedPostJson<{
      total: number; alta_confianza: number; media_confianza: number;
      baja_confianza: number; sin_clasificar: number;
      items: Array<{
        equipo_id: number; nombre: string; marca: string | null; modelo: string | null;
        foto_url: string | null; raiz: string | null; sub: string | null;
        raiz_id: number | null; sub_id: number | null;
        confianza: number; razon: string;
      }>;
    }>("/api/admin/equipos/clasificar-bulk", args),
  aplicarClasificacion: (asignaciones: Array<{ equipo_id: number; categoria_ids: number[] }>) =>
    authedPostJson<{
      aplicados: number;
      errores: Array<{ equipo_id: number; error: string }>;
      equipo_ids: number[];
    }>("/api/admin/equipos/aplicar-clasificacion", { asignaciones }),
  contarSinCategoria: () => authedJson<{ total: number }>("/api/admin/equipos/sin-categoria"),

  // ── Specs por equipo (PR D) ────────────────────────────────────────
  getEquipoSpecs: (id: number) =>
    authedJson<{
      equipo_id: number;
      specs: Record<string, string>;
      template: Array<{
        spec_key: string; label: string; tipo: string;
        unidad: string | null; enum_options: string[] | null;
        prioridad: number;
        visible_en_card: boolean; visible_en_filtros: boolean; visible_en_nombre: boolean;
        obligatorio: boolean; ayuda: string | null;
        categoria_nombre: string;
      }>;
    }>(`/api/admin/equipos/${id}/specs`),
  putEquipoSpecs: (id: number, specs: Record<string, string>) =>
    authedJson<{ ok: true; equipo_id: number; specs_count: number }>(
      `/api/admin/equipos/${id}/specs`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ specs }),
      },
    ),

  // ── CRUD templates de specs por categoría ──────────────────────────
  specTemplatesResumen: () =>
    authedJson<Record<number, number>>("/api/admin/spec-templates/resumen"),
  listSpecTemplates: (categoriaId: number) =>
    authedJson<{ items: SpecTemplate[] }>(`/api/admin/categorias/${categoriaId}/spec-templates`),
  listOrphanSpecs: (categoriaId: number) =>
    authedJson<OrphanSpec[]>(`/api/admin/categorias/${categoriaId}/spec-templates/orphans`),
  createSpecTemplate: (categoriaId: number, input: SpecTemplateInput) =>
    authedJson<SpecTemplate>(`/api/admin/categorias/${categoriaId}/spec-templates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  updateSpecTemplate: (templateId: number, input: Partial<SpecTemplateInput>) =>
    authedJson<{ ok: true; id: number }>(`/api/admin/spec-templates/${templateId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  reorderSpecTemplates: (items: { id: number; prioridad: number }[]) =>
    authedPostJson<{ ok: true; count: number }>(
      "/api/admin/spec-templates/reorder",
      { items },
    ),
  deleteSpecTemplate: async (templateId: number) => {
    const res = await authedFetch(`/api/admin/spec-templates/${templateId}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
  },

  // ── Compatibilidades ───────────────────────────────────────────────
  listarCompatibilidades: (id: number) =>
    authedJson<{
      items: Array<{
        id: number; otro_id: number; otro_nombre: string; otro_foto: string | null;
        tipo: "compatible" | "incompatible" | "requiere_adaptador";
        nota: string | null;
        adaptador_id: number | null; adaptador_nombre: string | null;
      }>;
    }>(`/api/admin/equipos/${id}/compatibilidades`),
  crearCompatibilidad: (
    id: number,
    data: {
      equipo_b_id: number;
      tipo: "compatible" | "incompatible" | "requiere_adaptador";
      nota?: string;
      adaptador_id?: number;
    },
  ) => authedPostJson<{ id: number }>(`/api/admin/equipos/${id}/compatibilidades`, data),
  borrarCompatibilidad: async (compat_id: number) => {
    const res = await authedFetch(`/api/admin/compatibilidades/${compat_id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail?.detail ?? `DELETE → ${res.status}`);
    }
  },

  // ── Nombres públicos / validación ──────────────────────────────────
  regenerarNombres: (dry_run = true) =>
    authedPostJson<{
      total: number;
      cambios: Array<{ id: number; nombre_interno: string; actual: string | null; nuevo: string; largo: string }>;
      sin_cambios: number;
      errores: Array<{ id: number; error: string }>;
      dry_run: boolean;
      cambios_truncados?: boolean;
      cambios_total?: number;
    }>("/api/admin/equipos/regenerar-nombres", { dry_run }),
  recalcularRanking: (args: { dry_run?: boolean; ventana_dias?: number } = {}) =>
    authedPostJson<{
      total: number; ventana_dias: number;
      cambios: Array<{
        id: number; nombre: string;
        antes: { score: number; pedidos: number; ingreso: number };
        despues: { score: number; pedidos: number; ingreso: number };
      }>;
      sin_cambios: number; dry_run: boolean;
    }>("/api/admin/equipos/recalcular-ranking", { dry_run: true, ventana_dias: 180, ...args }),
  listarParaValidacion: (filtro: "all" | "pendientes" | "aprobados" | "editados" = "all") =>
    authedJson<{
      items: Array<{
        id: number; nombre: string; marca: string | null; modelo: string | null;
        foto_url: string | null;
        nombre_publico: string | null;
        nombre_publico_largo: string | null;
        nombre_publico_override: string | null;
        revisado: boolean;
      }>;
      stats: { pendientes: number; aprobados: number; editados: number; total: number };
    }>(`/api/admin/equipos/nombres-validacion?filtro=${filtro}`),
  aprobarNombre: (id: number, args: { override?: string | null; revisado?: boolean } = {}) =>
    authedJson<{
      id: number;
      nombre_publico: string | null;
      nombre_publico_largo: string | null;
      nombre_publico_override: string | null;
      nombre_publico_revisado: boolean;
    }>(`/api/admin/equipos/${id}/nombre-publico`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        override: args.override ?? null,
        revisado: args.revisado !== false,
      }),
    }),

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

  // crear pedido nuevo (wizard / página /nuevo)
  createPedido: (data: PedidoCreateInput) => authedPostJson<Pedido>("/api/alquileres", data),

  // reemplazar items completos del pedido (PUT, requiere ≥1 ítem)
  updatePedidoItems: (
    id: number,
    items: { equipo_id: number; cantidad: number; precio_jornada: number }[],
  ) =>
    authedJson<Pedido>(`/api/alquileres/${id}/items`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    }),

  // clientes — detalle / edición
  getCliente: (id: number) => authedJson<Cliente>(`/api/clientes/${id}`),
  getClientePedidos: (id: number) =>
    authedJson<ClientePedidoRow[]>(`/api/clientes/${id}/pedidos`),
  updateCliente: (id: number, data: Partial<ClienteInput>) =>
    authedJson<Cliente>(`/api/clientes/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  deleteCliente: async (id: number) => {
    const res = await authedFetch(`/api/clientes/${id}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail?.detail ?? `DELETE → ${res.status}`);
    }
  },

  // calendario
  getCalendario: (desde: string, hasta: string) => {
    const sp = new URLSearchParams({ desde, hasta });
    return authedJson<CalendarioPedido[]>(`/api/calendario?${sp.toString()}`);
  },

  // estadísticas
  getEstadisticas: () => authedJson<EstadisticasData>("/api/estadisticas"),

  // settings — imports CSV
  importCsv: async (
    kind: "equipos" | "clientes" | "alquileres",
    file: File,
  ): Promise<ImportCsvResp> => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await authedFetch(`/api/settings/import-${kind}`, {
      method: "POST",
      body: fd,
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json?.detail ?? `Import ${kind} → ${res.status}`);
    return json as ImportCsvResp;
  },
  fixApellidos: () =>
    authedPostJson<{ ok: true; fixed?: number; message?: string }>(
      "/api/settings/fix-apellidos",
      {},
    ),
  resetClientesDesdeBackup: () =>
    authedPostJson<{ ok: true; message?: string }>(
      "/api/settings/reset-clientes-desde-backup",
      {},
    ),

  migrarStoragePaths: (dry_run: boolean) =>
    authedPostJson<{
      dry_run: boolean;
      to_rename?: number;
      moved?: number;
      db_updated?: number;
      errors?: number;
      error_detail?: { key: string; stage: string; error: string }[];
      skipped?: number;
      detail?: { equipo_id: number; old: string; new: string }[];
    }>(`/api/admin/storage/migrate-paths?dry_run=${dry_run}`, {}),

  uploadLogo: async (file: File): Promise<{ ok: true; url: string }> => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await authedFetch("/api/admin/settings/upload-logo", {
      method: "POST",
      body: fd,
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json?.detail ?? `Upload logo → ${res.status}`);
    return json as { ok: true; url: string };
  },
};

export type ClientePedidoRow = {
  id: number;
  numero_pedido: number | null;
  estado: PedidoEstado;
  fecha_desde: string | null;
  fecha_hasta: string | null;
  monto_total: number;
  monto_pagado: number;
  descuento_pct: number | null;
  equipos: string | null;
};

export type CalendarioPedido = {
  id: number;
  numero_pedido: number | null;
  cliente_nombre: string | null;
  estado: PedidoEstado;
  fecha_desde: string;
  fecha_hasta: string;
  monto_total: number;
  equipos: string | null;
};

export type EstadisticasData = {
  totales: {
    total_pedidos: number;
    total_clientes: number;
    total_ars: number;
    desde: string | null;
    hasta: string | null;
  };
  por_mes: { mes: string; pedidos: number; total_ars: number }[];
  crecimiento: { mes: string; total_ars: number; crecimiento_pct: number }[];
  top_equipos: { equipo: string; total_ars: number; veces: number }[];
  top_clientes: { cliente: string; total_ars: number; pedidos: number }[];
  clientes_recurrentes: { cliente: string; veces_alquiladas: number; total_ars: number }[];
  mejor_peor_mes: {
    mejor_mes: string | null; mejor_total: number | null;
    peor_mes: string | null; peor_total: number | null;
  };
  por_dueno: { dueno: string; total_ars: number; items: number }[];
};

export type ImportCsvResp = {
  ok?: boolean;
  success_count?: number;
  inserted?: number;
  updated?: number;
  skipped?: number;
  errors?: string[];
  error_details?: string[];
  message?: string;
  [k: string]: unknown;
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
  nombre_publico?: string | null;
  nombre_publico_largo?: string | null;
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

// ── Descuentos por jornadas ──────────────────────────────────────────────────

export type DescuentoJornada = { id: number; jornadas: number; pct: number };

export const descuentosJornadaApi = {
  list: () => authedJson<DescuentoJornada[]>("/api/descuentos-jornada"),
  create: (data: { jornadas: number; pct: number }) =>
    authedPostJson<DescuentoJornada>("/api/admin/descuentos-jornada", data),
  delete: (id: number) =>
    authedFetch(`/api/admin/descuentos-jornada/${id}`, { method: "DELETE" }),
};

