/**
 * API client para el backend rambla-rental (Python/FastAPI).
 *
 * VITE_API_URL:
 *   - Desarrollo: "http://localhost:5000"
 *   - Producción:  "" (el backend Python sirve el frontend en el mismo origen)
 */

const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

async function get<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(API_BASE + path, window.location.href);
  if (params) {
    Object.entries(params).forEach(([k, v]) => v && url.searchParams.set(k, v));
  }
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail ?? `POST ${path} → ${res.status}`);
  }
  return res.json();
}

/* ─── Tipos del backend ─────────────────────────────────────────────── */

export type BackendFicha = {
  descripcion: string | null;
  notas: string | null;
  specs_json: string | null;
  montura: string | null;
  formato: string | null;
  resolucion: string | null;
  keywords_json: string | null;
  nombre_publico_template?: string | null;
  // Ficha extendida (enriquecimiento)
  peso?: string | null;
  dimensiones?: string | null;
  alimentacion?: string | null;
  incluye_json?: string | null;
  conectividad_json?: string | null;
  compatible_con_json?: string | null;
  video_url?: string | null;
  precio_bh_usd?: number | null;
  fuente_url?: string | null;
  fuente_titulo?: string | null;
  enriquecido_at?: string | null;
  enriquecido_fuente?: string | null;
};

export type BackendCategoriaRef = {
  id: number;
  nombre: string;
  parent_id: number | null;
};

export type BackendMarca = {
  id: number;
  nombre: string;
  logo_url?: string | null;
  /** Score automático calculado por el ranking service (#131). */
  popularidad_score?: number;
};

export type BackendEquipo = {
  id: number;
  nombre: string;
  marca?: string;
  brand?: BackendMarca | null;
  modelo: string | null;
  cantidad: number;
  precio_jornada: number | null;
  precio_usd: number | null;
  foto_url: string | null;
  estado: string;
  visible_catalogo: number;
  relevancia_manual?: number;
  etiquetas: string[];
  kit: unknown[];
  categorias?: BackendCategoriaRef[];
  ficha?: BackendFicha;
  specs_destacados?: { label: string; value: string }[];
};

export type BackendCategoria = {
  id?: number;
  nombre: string;
  total: number;
  prioridad?: number;
  /** Score automático calculado por el ranking service (#131). */
  popularidad_score?: number;
  parent_id?: number | null;
  children?: BackendCategoria[];
  // Compat con respuesta legacy ?flat=1
  subtags?: { nombre: string; total: number }[];
};

export type Disponibilidad = Record<string, number>; // equipo_id (string) → unidades disponibles

/* ─── Endpoints ─────────────────────────────────────────────────────── */

export function apiGetEquipos() {
  return get<{ total: number; items: BackendEquipo[] }>("/api/equipos", {
    per_page: "500",
    solo_visibles: "true",
    sort: "ranking",
  });
}

export function apiGetCategorias() {
  return get<BackendCategoria[]>("/api/categorias");
}

export function apiGetDisponibilidad(fechaDesde: string, fechaHasta: string) {
  return get<Disponibilidad>("/api/disponibilidad", {
    fecha_desde: fechaDesde,
    fecha_hasta: fechaHasta,
  });
}

export function apiGetMarcs() {
  return get<{ items: BackendMarca[] }>("/api/marcas");
}

// NOTA: la creación de pedidos se movió a `src/lib/orders.ts → createOrder()`
// usando el endpoint autenticado /api/cliente/pedidos del backend FastAPI.
