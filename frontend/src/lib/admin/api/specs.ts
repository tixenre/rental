import { authedFetch, authedJson, authedPostJson } from "@/lib/authedFetch";
import type {
  CompatibleEquipo,
  CompatibleOverall,
  NoReconocidoGrupo,
  OrphanSpec,
  SpecDefinition,
  SpecDefinitionInput,
  SpecTemplate,
  SpecAssignmentInput,
  SpecAssignmentUpdate,
  Unidad,
  UnidadInput,
} from "./types";

export const specsMethods = {
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

  // ── Feed iCal de reservas (calendario suscribible) ────────────────────
  /** URL del feed iCal para suscribir en Google/Apple Calendar. Genera el
   *  token la primera vez que se consulta. */
  getCalendarFeed: () =>
    authedJson<{ url: string; token: string; enabled: boolean }>("/api/admin/calendar/feed"),
  /** Rota el token → invalida la URL anterior. */
  regenerateCalendarFeed: () =>
    authedPostJson<{ url: string; token: string; enabled: boolean }>(
      "/api/admin/calendar/feed/regenerate",
      {},
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
  /** Re-corre la extracción sobre el HTML YA guardado del equipo, sin
   *  resubir el archivo (#1203) — mismo shape que subir el HTML de nuevo.
   *  404 si el equipo no tiene HTML fuente guardado. */
  reExtractSpecs: (id: number) =>
    authedJson<{
      html_source_url: string;
      specs?: { label: string; value: string; spec_key?: string }[];
      unmatched?: { label: string; value: string }[];
      categoria_sugerida?: string | null;
    }>(`/api/admin/equipos/${id}/re-extract-specs`, { method: "POST" }),

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

  // ── Panel de specs no reconocidas (#1203) ───────────────────────────
  /** Specs sin match agrupadas por (categoría, label) — qué equipos las
   *  encontraron, valores de ejemplo. Une el productor CLI offline
   *  (agregado, equipos=[]) con el upload en vivo (uno por equipo). */
  listarNoReconocidos: () =>
    authedJson<{ items: NoReconocidoGrupo[] }>("/api/admin/specs/no-reconocidos"),
  /** Cierra en bloque las propuestas subyacentes de un grupo (bookkeeping —
   *  el spec/alias real se agrega al registry a mano y se re-siembra). */
  resolverNoReconocidos: (propuestaIds: number[], accion: "aplicado" | "descartado") =>
    authedPostJson<{ resueltas: number }>("/api/admin/specs/no-reconocidos/resolver", {
      propuesta_ids: propuestaIds,
      accion,
    }),

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
};
