/**
 * Admin API client — wrappers tipados de los endpoints del back-office FastAPI.
 *
 * Todos requieren JWT de Supabase con email en ADMIN_EMAILS (validado por
 * `require_admin` en backend/supabase_auth.py), salvo cuando el backend
 * tiene ADMIN_BYPASS_AUTH=1.
 */

import { authedFetch, authedJson, authedPostJson } from "@/lib/authedFetch";
import type { EstadoPedido } from "@/lib/pedido-estados";
export type { EstadoPedido };

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
  descripcion: string | null;
  notas: string | null;
  keywords_json: string | null;
  nombre_publico_template?: string | null;
  // Listas / multimedia del enriquecimiento (no son specs estructuradas)
  incluye_json?: string | null;
  conectividad_json?: string | null;
  compatible_con_json?: string | null;
  video_url?: string | null;
  precio_bh_usd?: number | null;
  fuente_url?: string | null;
  fuente_titulo?: string | null;
  enriquecido_at?: string | null;
  enriquecido_fuente?: string | null;
  // Fase F: montura/formato/resolucion/peso/dimensiones/alimentacion
  // se droppearon de equipo_fichas. Las specs viven en equipo_specs.
  // B1 #635: contenido incluido (dim. 3) — [{nombre, cantidad, foto_url?}]
  contenido_incluido_json?: string | null;
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
  /** Categoría de specs (1 de las 5 del registry): define qué specs aplican
   *  y el nombre público. Independiente del árbol de categorías de catálogo
   *  (`categorias`), que es solo agrupación para el front-office. */
  categoria_specs?: string | null;
  /** Tipo de producto. Gobierna precio, stock y disponibilidad.
   *  'simple' = equipo suelto · 'kit' = con accesorios compartidos · 'combo' = agrupación derivada. */
  tipo?: "simple" | "kit" | "combo";
  /** URL pública del HTML de producto guardado en R2 (para re-extracción futura). */
  html_source_url?: string | null;
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
  /** Descuento % por línea (para combos — fase C3). */
  descuento_pct?: number | null;
  /** True = esencial (falta → combo no disponible); False = best-effort (fase C2). */
  esencial?: boolean | null;
};

export type EquiposListResp = {
  total: number;
  page: number;
  per_page: number;
  items: Equipo[];
};

export type EquipoInput = Partial<
  Omit<Equipo, "id" | "etiquetas" | "kit" | "categorias" | "ficha">
> & {
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
  fecha_hasta: string | null;
  cantidad: number;
  bloquea_stock: boolean;
  created_at?: string;
};

export type MantenimientoInput = {
  fecha: string;
  tipo?: string;
  descripcion?: string | null;
  costo?: number | null;
  proxima_revision?: string | null;
  fecha_hasta?: string | null;
  cantidad?: number;
  bloquea_stock?: boolean;
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

export type SpecTipo =
  | "string"
  | "number"
  | "enum"
  | "bool"
  | "rango"
  | "wxh"
  | "wxhxd"
  | "multi_enum"
  | "tabla";

/** Tipo de una columna individual cuando spec_definitions.tipo='tabla'.
 *  - `valor_unidad`: la celda tiene 2 sub-campos (número + unidad), permite
 *    que la unidad varíe por fila (ej. 10000 lumen / 8000 lumen). */
export type SpecTablaColTipo = "string" | "number" | "enum" | "bool" | "valor_unidad";

/** Una columna de una spec tipo tabla. Define qué se carga en cada celda
 *  y cómo se renderiza el input. */
export type SpecTablaColumna = {
  key: string;
  label: string;
  tipo: SpecTablaColTipo;
  /** Para tipo='enum': opciones permitidas. */
  options?: string[];
  /** Sufijo visual (lm, °C, etc.). Solo para tipos escalares. */
  unidad?: string | null;
  /** Para tipo='valor_unidad': lista cerrada de unidades permitidas. Si está
   *  definida, el input de unidad se renderiza como select. Si no, input libre. */
  unidades_opciones?: string[];
  /** Texto fijo que aparece ANTES del valor — sirve como conector textual
   *  entre columnas. Ej. col2.prefijo="a" → "10000 lm a 5700 K". */
  prefijo?: string | null;
};

/** Definición global de una spec (post refactor unificar_specs_definitions).
 *  Cada spec_key existe UNA sola vez en el sistema. Sus categorías la
 *  referencian via spec_def_id en la asignación. */
export type CompatibilidadModo = "exacta" | "jerarquia";
export type RolCompatibilidad = "contenedor" | "contenido" | null;

/** Config declarativa de cómo se rinde la spec en un placeholder {spec:Label}.
 *  Aplicada por backend/services/spec_render.py y mirroreada en
 *  src/lib/equipment/nombre-template.ts. */
export type SpecRowStrategy = "all" | "first" | "last";
export type SpecOutputConfig = {
  /** Solo aplica a tipo='tabla'. Default 'all'. */
  row_strategy?: SpecRowStrategy;
};

/** Asignación de una spec a una categoría (con su template_id para poder
 *  desasignar desde el modal de edición). */
export type SpecDefinitionCategoriaAsign = {
  id: number;
  nombre: string;
  template_id: number;
  /** Flags por categoría — el detalle vive en "Specs por categoría". Solo
   *  los exponemos acá para que el modal global muestre inline si tienen
   *  override por categoría (read-only). */
  destacado: boolean;
  prioridad: number;
  ayuda: string | null;
};

export type SpecDefinition = {
  id: number;
  spec_key: string;
  label: string;
  tipo: SpecTipo;
  unidad: string | null;
  /** FK al catálogo `unidades` (sync con el string `unidad` por el backend).
   *  null si la spec no tiene unidad asociada. */
  unidad_id: number | null;
  enum_options: string[] | null;
  ayuda: string | null;
  es_compatibilidad: boolean;
  compatibilidad_modo: CompatibilidadModo;
  /** Flag manual: el dueño la revisó y aprobó. Se ordenan arriba. */
  validado: boolean;
  /** Solo para tipo='tabla': shape de las columnas. */
  tabla_columnas: SpecTablaColumna[] | null;
  /** Config declarativa de render del placeholder. Solo `row_strategy` por ahora. */
  output_config: SpecOutputConfig | null;
  /** Solo en GET /admin/spec-definitions: cuántas categorías la asignaron. */
  uso_categorias?: number;
  /** Solo en GET /admin/spec-definitions: cuántos equipos tienen value. */
  uso_equipos?: number;
  /** Solo en GET: categorías que la asignan (con id + nombre + template_id). */
  categorias?: SpecDefinitionCategoriaAsign[];
};

/** Una unidad del catálogo global (lm, K, V…). */
export type Unidad = {
  id: number;
  simbolo: string;
  nombre: string;
  dimension: string | null;
};

export type UnidadInput = {
  simbolo: string;
  nombre: string;
  dimension?: string | null;
};

export type SpecDefinitionInput = {
  spec_key: string;
  label: string;
  tipo: SpecTipo;
  unidad?: string | null;
  enum_options?: string[] | null;
  ayuda?: string | null;
  es_compatibilidad?: boolean;
  compatibilidad_modo?: CompatibilidadModo;
  validado?: boolean;
  tabla_columnas?: SpecTablaColumna[] | null;
  output_config?: SpecOutputConfig | null;
};

/** Asignación de una spec_def a una categoría + flags propios. El backend
 *  hace JOIN con spec_definitions y proyecta los campos descriptivos
 *  (spec_key/label/tipo/unidad/enum_options) acá para que el frontend
 *  los use sin un fetch extra. */
export type SpecTemplate = {
  id: number;
  categoria_id: number;
  spec_def_id: number;
  // Proyectados desde spec_definitions:
  spec_key: string;
  label: string;
  tipo: SpecTipo;
  unidad: string | null;
  unidad_id: number | null;
  enum_options: string[] | null;
  tabla_columnas: SpecTablaColumna[] | null;
  output_config: SpecOutputConfig | null;
  es_compatibilidad: boolean;
  compatibilidad_modo: CompatibilidadModo;
  // Per-categoría: (los flags aplicados por la asignación)
  prioridad: number;
  visible_en_card: boolean;
  visible_en_filtros: boolean;
  visible_en_nombre: boolean;
  obligatorio: boolean;
  ayuda: string | null;
  destacado: boolean;
  rol_compatibilidad: RolCompatibilidad;
};

/** Body para asignar una spec ya existente a una categoría. */
export type SpecAssignmentInput = {
  spec_def_id: number;
  prioridad?: number;
  destacado?: boolean;
  obligatorio?: boolean;
  visible_en_card?: boolean;
  visible_en_filtros?: boolean;
  visible_en_nombre?: boolean;
  ayuda?: string | null;
  rol_compatibilidad?: RolCompatibilidad;
};

/** Body para editar los flags de una asignación. */
export type SpecAssignmentUpdate = {
  prioridad?: number;
  destacado?: boolean;
  obligatorio?: boolean;
  visible_en_card?: boolean;
  visible_en_filtros?: boolean;
  visible_en_nombre?: boolean;
  ayuda?: string | null;
  rol_compatibilidad?: RolCompatibilidad;
};

/** Compat alias: el SpecTemplatesSection viejo usaba SpecTemplateInput. Lo
 *  mantengo como alias para no romper imports — pero los nuevos callers
 *  deben usar SpecAssignmentInput o SpecDefinitionInput según contexto. */
export type SpecTemplateInput = SpecAssignmentInput;

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
  spec_def_id: number;
  spec_key: string;
  label: string;
  count_equipos: number;
  sample_values: string[];
};

/** Overall status de la compatibilidad automática.
 *  - compatible: todas las specs comparten valor exacto.
 *  - compatible_con_crop: jerárquica donde el contenedor proyecta más grande
 *    que el contenido (lente FF en sensor APS-C ⇒ crop central, usable).
 *  - parcial: viñetea u otra mismatch jerárquica con roles definidos.
 *  - incompatible: alguna spec exacta no matchea, o manual override negativo.
 *  - requiere_adaptador: manual `equipo_compatibilidad` con adaptador linkeado.
 *  - sin_relacion: no comparten specs con es_compatibilidad=true. */
export type CompatibleOverall =
  | "compatible"
  | "compatible_con_crop"
  | "parcial"
  | "incompatible"
  | "requiere_adaptador"
  | "sin_relacion";

export type CompatibleRazon = {
  spec: string;
  status: "match" | "match_con_crop" | "mismatch" | "partial_vignette" | "partial";
  mensaje: string;
};

export type CompatibleEquipo = {
  equipo_id: number;
  nombre: string;
  foto_url: string | null;
  marca: string | null;
  overall: CompatibleOverall;
  razones: CompatibleRazon[];
  adaptador?: { id: number; nombre: string } | null;
};

// ── Propuestas IA del skill gear-compatibility ──────────────────────
export type PropuestaTipo = "enum_option" | "spec_nueva" | "merge_specs" | "assign_spec";

/** Una propuesta pendiente generada por el skill `gear-compatibility`.
 *  Hasta aplicarla, no afecta el catálogo. El payload varía por tipo. */
export type PropuestaPendiente = {
  id: number;
  tipo: PropuestaTipo;
  payload: Record<string, unknown>;
  origen: string | null;
  confianza: number | null;
  created_at: string;
  aplicado_at: string | null;
  descartado_at: string | null;
};

/** Equipo pendiente de análisis de compatibilidad. Lo lista el skill
 *  cuando se invoca `/gear-compat new`. */
export type EquipoPendienteCompat = {
  id: number;
  nombre: string;
  marca: string | null;
  modelo: string | null;
  categorias: string[];
  compat_analizado_at: string | null;
  motivo: "nunca_analizado" | "modificado" | "al_dia";
};

export const adminApi = {
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
      descuento_pct: descuento_pct ?? null,
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

  // ── App settings (key/value globales) ─────────────────────────────────
  getSetting: (key: string) =>
    authedJson<{
      key: string;
      value: string;
      updated_at: string | null;
      updated_by: string | null;
    }>(`/api/settings/${encodeURIComponent(key)}`),
  listSettings: () =>
    authedJson<{
      items: Array<{
        key: string;
        value: string;
        updated_at: string | null;
        updated_by: string | null;
      }>;
    }>("/api/settings"),
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
  recalcularPrecios: (args: {
    dry_run: boolean;
    mode?: "missing" | "auto" | "all" | "ids";
    ids?: number[];
  }) =>
    authedPostJson<{
      usd_rate: number;
      mode: string;
      total_evaluados: number;
      total_cambios: number;
      cambios: Array<{
        id: number;
        nombre: string;
        antes: number | null;
        despues: number;
        delta: number;
        manual: boolean;
      }>;
      dry_run: boolean;
    }>("/api/admin/settings/recalcular-precios", args),
  /** Lista equipos con precio manual + lo que daría la fórmula con el
   *  USD rate actual. Útil para revisión equipo-por-equipo. */
  listarPreciosManuales: () =>
    authedJson<{
      usd_rate: number;
      items: Array<{
        id: number;
        nombre: string;
        marca: string | null;
        modelo: string | null;
        foto_url: string | null;
        precio_actual: number | null;
        precio_usd: number | null;
        roi_pct: number | null;
        precio_calculado: number | null;
        delta: number | null;
      }>;
    }>("/api/admin/equipos/precios-manuales"),

  // ── Clasificación (PR C) ───────────────────────────────────────────
  clasificarBulk: (args: { solo_sin_categoria?: boolean; equipo_ids?: number[] } = {}) =>
    authedPostJson<{
      total: number;
      alta_confianza: number;
      media_confianza: number;
      baja_confianza: number;
      sin_clasificar: number;
      items: Array<{
        equipo_id: number;
        nombre: string;
        marca: string | null;
        modelo: string | null;
        foto_url: string | null;
        raiz: string | null;
        sub: string | null;
        raiz_id: number | null;
        sub_id: number | null;
        confianza: number;
        razon: string;
      }>;
    }>("/api/admin/equipos/clasificar-bulk", args),
  aplicarClasificacion: (asignaciones: Array<{ equipo_id: number; categoria_ids: number[] }>) =>
    authedPostJson<{
      aplicados: number;
      errores: Array<{ equipo_id: number; error: string }>;
      equipo_ids: number[];
    }>("/api/admin/equipos/aplicar-clasificacion", { asignaciones }),
  contarSinCategoria: () => authedJson<{ total: number }>("/api/admin/equipos/sin-categoria"),

  // ── Specs por equipo ───────────────────────────────────────────────
  // Post refactor: specs keyed por spec_def_id (string del int). El backend
  // proyecta los campos descriptivos (spec_key/label/tipo/...) desde
  // spec_definitions vía JOIN.
  getEquipoSpecs: (id: number) =>
    authedJson<{
      equipo_id: number;
      /** Keys son spec_def_id stringificados ("123": "valor"). */
      specs: Record<string, string>;
      /** Template aplicable a las categorías del equipo (resuelto vía
       *  WITH RECURSIVE en el backend). El shape extiende SpecTemplate
       *  con `template_id` (alias legacy de `id`) y `categoria_nombre`
       *  (para agrupar en UI). */
      template: Array<
        SpecTemplate & {
          template_id: number;
          categoria_nombre: string;
        }
      >;
    }>(`/api/admin/equipos/${id}/specs`),
  /** Reemplaza TODAS las specs del equipo. Las keys son spec_def_id como
   *  strings (JSON no permite int keys). */
  putEquipoSpecs: (id: number, specs: Record<string, string>) =>
    authedJson<{ ok: true; equipo_id: number; specs_count: number }>(
      `/api/admin/equipos/${id}/specs`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ specs }),
      },
    ),

  // ── Observatorio de specs (relevamiento de scrapes reales) ─────────
  recomputeObservatorio: () =>
    authedJson<{
      equipos_procesados: number;
      observaciones_insertadas: number;
      labels_unicos: number;
      sin_raw_json: number;
    }>("/api/admin/specs/observatorio/recompute", { method: "POST" }),
  observatorioStats: () =>
    authedJson<{
      total_obs: number;
      equipos_cubiertos: number;
      labels_unicos: number;
      matched_count: number;
      unmatched_count: number;
      equipos_con_raw_json: number;
      equipos_scrapeables_pendientes: number;
      equipos_total: number;
      last_observed_at: string | null;
    }>("/api/admin/specs/observatorio/stats"),
  observatorioScrapeablesPendientes: () =>
    authedJson<{
      total: number;
      ids: number[];
      items: Array<{ id: number; nombre: string; bh_url: string | null }>;
    }>("/api/admin/specs/observatorio/scrapeables-pendientes"),
  observatorioAgregado: (
    params: {
      categoria?: string | null;
      solo_unmapped?: boolean;
      top_values?: number;
    } = {},
  ) => {
    const qs = new URLSearchParams();
    if (params.categoria) qs.set("categoria", params.categoria);
    if (params.solo_unmapped) qs.set("solo_unmapped", "true");
    if (params.top_values) qs.set("top_values", String(params.top_values));
    return authedJson<{
      total: number;
      items: Array<{
        categoria_raiz: string | null;
        label_observado: string;
        label_normalizado: string;
        equipos_count: number;
        matched_template: boolean;
        spec_def_id: number | null;
        top_values: Array<{ value: string; count: number }>;
      }>;
    }>(`/api/admin/specs/observatorio/agregado?${qs.toString()}`);
  },

  // ── Catálogo global de spec_definitions ────────────────────────────
  listSpecDefinitions: () => authedJson<{ items: SpecDefinition[] }>("/api/admin/spec-definitions"),
  createSpecDefinition: (input: SpecDefinitionInput) =>
    authedJson<SpecDefinition>("/api/admin/spec-definitions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  updateSpecDefinition: (defId: number, input: Partial<SpecDefinitionInput>) =>
    authedJson<{ ok: true; id: number }>(`/api/admin/spec-definitions/${defId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  deleteSpecDefinition: async (defId: number) => {
    const res = await authedFetch(`/api/admin/spec-definitions/${defId}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      const body = await res.text();
      throw new Error(body || `HTTP ${res.status}`);
    }
  },

  // ── Catálogo global de unidades (lm, K, V, etc.) ───────────────────
  listUnidades: () => authedJson<{ items: Unidad[] }>("/api/admin/unidades"),
  createUnidad: (input: UnidadInput) =>
    authedJson<Unidad>("/api/admin/unidades", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  updateUnidad: (unidadId: number, input: Partial<UnidadInput>) =>
    authedJson<{ ok: true; id: number }>(`/api/admin/unidades/${unidadId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  deleteUnidad: async (unidadId: number) => {
    const res = await authedFetch(`/api/admin/unidades/${unidadId}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      const body = await res.text();
      throw new Error(body || `HTTP ${res.status}`);
    }
  },

  // ── CRUD asignaciones de spec_def a categorías ─────────────────────
  specTemplatesResumen: () =>
    authedJson<Record<number, number>>("/api/admin/spec-templates/resumen"),
  listSpecTemplates: (categoriaId: number) =>
    authedJson<{ items: SpecTemplate[] }>(`/api/admin/categorias/${categoriaId}/spec-templates`),
  /** Categorías FUNCIONALES (las del registry con specs sembradas). Fuente
   *  canónica para el selector "Categoría de specs" del form de equipos:
   *  cada una trae su id real para fetchear el spec-template. */
  listSpecCategorias: () =>
    authedJson<{ categorias: { id: number; nombre: string }[] }>("/api/admin/specs/por-categoria"),
  listOrphanSpecs: (categoriaId: number) =>
    authedJson<OrphanSpec[]>(`/api/admin/categorias/${categoriaId}/spec-templates/orphans`),
  /** Asigna una spec_definition existente a una categoría. Para crear una
   *  spec nueva globalmente usar createSpecDefinition primero. */
  assignSpecToCategoria: (categoriaId: number, input: SpecAssignmentInput) =>
    authedJson<SpecTemplate>(`/api/admin/categorias/${categoriaId}/spec-templates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  /** Alias retro-compat: createSpecTemplate ahora redirige a assign. Los
   *  callers viejos que pasaban SpecTemplateInput (~ SpecAssignmentInput)
   *  siguen funcionando. */
  createSpecTemplate: (categoriaId: number, input: SpecAssignmentInput) =>
    authedJson<SpecTemplate>(`/api/admin/categorias/${categoriaId}/spec-templates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  updateSpecTemplate: (templateId: number, input: SpecAssignmentUpdate) =>
    authedJson<{ ok: true; id: number }>(`/api/admin/spec-templates/${templateId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  reorderSpecTemplates: (items: { id: number; prioridad: number }[]) =>
    authedPostJson<{ ok: true; count: number }>("/api/admin/spec-templates/reorder", { items }),
  deleteSpecTemplate: async (templateId: number) => {
    const res = await authedFetch(`/api/admin/spec-templates/${templateId}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
  },

  // ── Compatibilidades ───────────────────────────────────────────────
  listarCompatibilidades: (id: number) =>
    authedJson<{
      items: Array<{
        id: number;
        otro_id: number;
        otro_nombre: string;
        otro_foto: string | null;
        tipo: "compatible" | "incompatible" | "requiere_adaptador";
        nota: string | null;
        adaptador_id: number | null;
        adaptador_nombre: string | null;
        auto_generado?: boolean;
        razon_ia?: string | null;
        confianza?: number | null;
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
  /** Compatibilidad automática derivada de specs (modo exacta + jerárquica
   *  con roles contenedor/contenido) + merge con manual `equipo_compatibilidad`.
   *  El backend agrupa por overall y ya devuelve razones legibles. */
  listarCompatiblesAuto: (
    id: number,
    params: { categoria_id?: number; overall_min?: CompatibleOverall } = {},
  ) => {
    const sp = new URLSearchParams();
    if (params.categoria_id) sp.set("categoria_id", String(params.categoria_id));
    if (params.overall_min) sp.set("overall_min", params.overall_min);
    const qs = sp.toString();
    return authedJson<{ items: CompatibleEquipo[] }>(
      `/api/admin/equipos/${id}/compatibles${qs ? `?${qs}` : ""}`,
    );
  },

  // ── Nombres públicos / validación ──────────────────────────────────
  regenerarNombres: (dry_run = true) =>
    authedPostJson<{
      total: number;
      cambios: Array<{
        id: number;
        nombre_interno: string;
        actual: string | null;
        nuevo: string;
        largo: string;
      }>;
      sin_cambios: number;
      errores: Array<{ id: number; error: string }>;
      dry_run: boolean;
      cambios_truncados?: boolean;
      cambios_total?: number;
    }>("/api/admin/equipos/regenerar-nombres", { dry_run }),
  recalcularRanking: (args: { dry_run?: boolean; ventana_dias?: number } = {}) =>
    authedPostJson<{
      total: number;
      ventana_dias: number;
      cambios: Array<{
        id: number;
        nombre: string;
        antes: { score: number; pedidos: number; ingreso: number };
        despues: { score: number; pedidos: number; ingreso: number };
      }>;
      sin_cambios: number;
      dry_run: boolean;
    }>("/api/admin/equipos/recalcular-ranking", { dry_run: true, ventana_dias: 180, ...args }),
  listarParaValidacion: (filtro: "all" | "pendientes" | "aprobados" | "editados" = "all") =>
    authedJson<{
      items: Array<{
        id: number;
        nombre: string;
        marca: string | null;
        modelo: string | null;
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
  listPedidos: (
    params: {
      estado?: string;
      q?: string;
      con_saldo?: boolean;
      per_page?: number;
      page?: number;
    } = {},
  ) => {
    const sp = new URLSearchParams();
    if (params.estado) sp.set("estado", params.estado);
    if (params.q) sp.set("q", params.q);
    if (params.con_saldo) sp.set("con_saldo", "true");
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
  getDisponibilidad: (fechaDesde: string, fechaHasta: string, excludePedidoId?: number) => {
    const sp = new URLSearchParams({ fecha_desde: fechaDesde, fecha_hasta: fechaHasta });
    if (excludePedidoId) sp.set("exclude_pedido_id", String(excludePedidoId));
    // El backend devuelve `{ equipo_id: libres }` — número neto (ya descontadas
    // reservas + mantenimiento), no `{cantidad, reservado}`. El consumidor lo
    // adapta. Ver `reservas.calcular_disponibilidad`.
    return authedJson<Record<string, number>>(`/api/disponibilidad?${sp.toString()}`);
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
  getClientePedidos: (id: number) => authedJson<ClientePedidoRow[]>(`/api/clientes/${id}/pedidos`),
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

  // analítica de búsquedas del catálogo público
  getBusquedas: (dias?: number) =>
    authedJson<BusquedasData>(`/api/admin/busquedas${dias && dias > 0 ? `?dias=${dias}` : ""}`),

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

  uploadOgImage: async (file: File): Promise<{ ok: true; url: string }> => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await authedFetch("/api/admin/settings/upload-og-image", {
      method: "POST",
      body: fd,
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(json?.detail ?? `Upload OG image → ${res.status}`);
    return json as { ok: true; url: string };
  },

  // ── Email templates ─────────────────────────────────────────────────
  listEmailTemplates: () =>
    authedJson<{ items: EmailTemplateSummary[] }>("/api/admin/email-templates"),
  getEmailTemplate: (key: string) =>
    authedJson<EmailTemplate>(`/api/admin/email-templates/${encodeURIComponent(key)}`),
  updateEmailTemplate: (key: string, input: EmailTemplateInput) =>
    authedJson<EmailTemplate>(`/api/admin/email-templates/${encodeURIComponent(key)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  previewEmailTemplate: (key: string, context?: Record<string, unknown>) =>
    authedJson<{ subject: string; html: string; text: string }>(
      `/api/admin/email-templates/${encodeURIComponent(key)}/preview`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ context: context ?? null }),
      },
    ),
  testEmailTemplate: (key: string, to: string, context?: Record<string, unknown>) =>
    authedJson<{
      ok: boolean;
      provider?: string;
      provider_id?: string;
      error?: string;
      log_id?: number;
    }>(`/api/admin/email-templates/${encodeURIComponent(key)}/test`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ to, context: context ?? null }),
    }),
};

export type EmailTemplateSummary = {
  key: string;
  subject: string;
  updated_at: string;
  updated_by: string | null;
};

export type EmailTemplate = EmailTemplateSummary & {
  body_html: string;
  body_text: string;
};

export type EmailTemplateInput = {
  subject: string;
  body_html: string;
  body_text: string;
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

/** Una fila agregada de búsquedas: un término normalizado con cuántas veces se
 *  buscó, un ejemplo del texto crudo, la última vez, y (en `top`) el máximo de
 *  resultados que llegó a dar. */
export type BusquedaRow = {
  query_norm: string;
  veces: number;
  texto: string;
  ultima: string | null;
  max_resultados?: number;
};

export type BusquedasData = {
  top: BusquedaRow[];
  zero: BusquedaRow[];
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
    mejor_mes: string | null;
    mejor_total: number | null;
    peor_mes: string | null;
    peor_total: number | null;
  };
  por_dueno: { dueno: string; total_ars: number; items: number }[];
  favoritos_equipo?: { equipo: string; total_favoritos: number; clientes_unicos: number }[];
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
  total: number;
  page: number;
  per_page: number;
  items: Cliente[];
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

/** @deprecated Usar EstadoPedido importado de @/lib/pedido-estados */
export type PedidoEstado = EstadoPedido;

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
  cliente_perfil_impuestos: string | null;
  fecha_desde: string | null;
  fecha_hasta: string | null;
  estado: PedidoEstado;
  fuente: string | null;
  monto_total: number;
  monto_pagado: number;
  descuento_pct: number | null;
  descuento_jornadas_pct: number | null;
  notas: string | null;
  created_at?: string;
  items: PedidoItem[];
  pagos?: PedidoPago[];
  /** True si hay una `solicitudes_modificacion` con estado='pendiente' para
   * este pedido. Sólo viene en el listado, no en el detalle. */
  tiene_solicitud_pendiente?: boolean;
  /** Solo presente en el detalle (`getPedido`). Timeline de cambios del
   * cliente desde el portal. */
  historial_modificaciones?: PedidoHistorialItem[];
  // Desglose canónico del total — viene del backend
  // (services/precios.calcular_total). El frontend lo lee directo sin
  // reimplementar la fórmula (#496).
  bruto?: number;
  descuento_monto?: number;
  monto_neto?: number;
  iva_pct?: number;
  iva_monto?: number;
  total_con_iva?: number;
  con_iva?: boolean;
  cantidad_jornadas?: number;
};

export type PedidoCambiosSnapshot = {
  fecha_desde?: string | null;
  fecha_hasta?: string | null;
  items?: { equipo_id: number; cantidad: number }[];
  mensaje?: string | null;
};

export type PedidoHistorialItem = {
  id: number;
  mensaje: string | null;
  estado: "pendiente" | "aprobada" | "rechazada" | "cancelada";
  respuesta: string | null;
  cambios_json: PedidoCambiosSnapshot | null;
  /** Lo que efectivamente se aplicó al aprobar (≠ cambios_json si admin
   *  envió contrapropuesta). null si la solicitud no se aprobó. */
  cambios_aplicados: PedidoCambiosSnapshot | null;
  tipo: "directo" | "aprobacion";
  resolved_at: string | null;
  resolved_by: string | null;
  created_at: string;
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
export const pedidoPdfUrl = (
  id: number,
  kind: "pdf" | "albaran" | "contrato" | "packing-list" = "pdf",
) => `${API_BASE}/api/alquileres/${id}/${kind}`;

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

// ── Estudio (singleton E1) ───────────────────────────────────────────────────

export type EstudioFoto = {
  id: number;
  url: string;
  path: string | null;
  orden: number;
  es_principal: boolean;
  created_at: string | null;
};

export type EstudioConfig = {
  id: number;
  equipo_id: number | null;
  nombre: string;
  tagline: string;
  descripcion: string;
  precio_hora: number;
  min_horas: number;
  open_hour: number;
  close_hour: number;
  buffer_horas: number;
  anticipacion_min_horas: number;
  pack_activo: boolean;
  pack_nombre: string;
  pack_descripcion: string;
  pack_precio: number;
  features: Array<{ label: string; value: string }> | null;
  faq: Array<{ q: string; a: string }> | null;
  direccion: string;
  como_llegar: string;
  testimonios: Array<{ autor: string; texto: string }> | null;
  mapa_url: string;
  mapa_embed_url: string;
  updated_at: string | null;
  fotos: EstudioFoto[];
};

export type EstudioInput = {
  nombre?: string;
  tagline?: string;
  descripcion?: string;
  precio_hora?: number;
  min_horas?: number;
  open_hour?: number;
  close_hour?: number;
  buffer_horas?: number;
  anticipacion_min_horas?: number;
  pack_activo?: boolean;
  pack_nombre?: string;
  pack_descripcion?: string;
  pack_precio?: number;
  features_json?: string;
  faq_json?: string;
  direccion?: string;
  como_llegar?: string;
  testimonios_json?: string;
  mapa_url?: string;
};

export type FotoOrdenItem = { id: number; orden: number; es_principal: boolean };

export type EstudioSlotFijo = {
  id: number;
  cliente: string;
  dia_semana: number; // 0=Lun .. 6=Dom
  hora_desde: number;
  hora_hasta: number;
  valor_mensual: number;
  mes_desde: string; // YYYY-MM
  mes_hasta: string; // YYYY-MM
  activo: boolean;
};

export type EstudioSlotInput = Omit<EstudioSlotFijo, "id">;

export type EstudioPackEquipoCurado = {
  id: number;
  nombre: string;
  marca: string | null;
  foto_url: string | null;
  orden: number;
};

export const estudioAdminApi = {
  get: () => authedJson<EstudioConfig>("/api/estudio"),
  listPack: () => authedJson<{ pack: EstudioPackEquipoCurado[] }>("/api/admin/estudio/pack"),
  addPackEquipo: (equipo_id: number) =>
    authedPostJson<{ pack: EstudioPackEquipoCurado[] }>("/api/admin/estudio/pack", { equipo_id }),
  removePackEquipo: (equipo_id: number) =>
    authedFetch(`/api/admin/estudio/pack/${equipo_id}`, { method: "DELETE" }).then(async (r) => {
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d?.detail ?? `DELETE pack → ${r.status}`);
      }
      return r.json() as Promise<{ pack: EstudioPackEquipoCurado[] }>;
    }),
  listSlots: () => authedJson<{ slots: EstudioSlotFijo[] }>("/api/admin/estudio/slots"),
  createSlot: (data: EstudioSlotInput) =>
    authedPostJson<EstudioSlotFijo>("/api/admin/estudio/slots", data),
  updateSlot: (id: number, data: Partial<EstudioSlotInput>) =>
    authedFetch(`/api/admin/estudio/slots/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(async (r) => {
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d?.detail ?? `PATCH slot → ${r.status}`);
      }
      return r.json() as Promise<EstudioSlotFijo>;
    }),
  deleteSlot: (id: number) =>
    authedFetch(`/api/admin/estudio/slots/${id}`, { method: "DELETE" }).then(async (r) => {
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d?.detail ?? `DELETE slot → ${r.status}`);
      }
      return r.json() as Promise<{ ok: boolean }>;
    }),
  update: (data: EstudioInput) =>
    authedFetch("/api/admin/estudio", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(async (r) => {
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d?.detail ?? `PATCH estudio → ${r.status}`);
      }
      return r.json() as Promise<EstudioConfig>;
    }),
  deleteFoto: (fotoId: number) =>
    authedFetch(`/api/admin/estudio/fotos/${fotoId}`, { method: "DELETE" }).then(async (r) => {
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d?.detail ?? `DELETE foto → ${r.status}`);
      }
      return r.json() as Promise<{ ok: boolean }>;
    }),
  reorderFotos: (fotos: FotoOrdenItem[]) =>
    authedFetch("/api/admin/estudio/fotos/orden", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fotos }),
    }).then(async (r) => {
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d?.detail ?? `PATCH fotos/orden → ${r.status}`);
      }
      return r.json() as Promise<{ fotos: EstudioFoto[] }>;
    }),
};

// ── Descuentos por jornadas ──────────────────────────────────────────────────

export type DescuentoJornada = { id: number; jornadas: number; pct: number };

export const descuentosJornadaApi = {
  list: () => authedJson<DescuentoJornada[]>("/api/descuentos-jornada"),
  create: (data: { jornadas: number; pct: number }) =>
    authedPostJson<DescuentoJornada>("/api/admin/descuentos-jornada", data),
  delete: (id: number) => authedFetch(`/api/admin/descuentos-jornada/${id}`, { method: "DELETE" }),
};
