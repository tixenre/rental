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
  keywords_json: string | null;
  nombre_publico_template?: string | null;
  // Listas estructuradas que aún no son specs (Fase G migración futura)
  incluye_json?: string | null;
  conectividad_json?: string | null;
  compatible_con_json?: string | null;
  // Multimedia y referencias (no son specs estructuradas)
  video_url?: string | null;
  precio_bh_usd?: number | null;
  fuente_url?: string | null;
  fuente_titulo?: string | null;
  enriquecido_at?: string | null;
  enriquecido_fuente?: string | null;
  // Columnas legacy montura/formato/resolucion/peso/dimensiones/alimentacion
  // se droppearon en Fase F — las specs viven en equipo_specs.
  // specs_json y raw_json se droppearon en Fase E.
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
  /** Curación manual del admin para BrandCarousel del home. #288 */
  destacada?: boolean;
  /** Orden manual del admin (drag-drop en /admin/equipos/marcas). */
  orden?: number;
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
  /** Specs estructuradas (Fase D): dict keyed por spec_key, fuente única
   *  post-migración. Reemplaza specs_json + columnas legacy de ficha. */
  specs?: Record<
    string,
    {
      label: string;
      value: string;
      /** Valor renderizado para display (mismo renderer que el nombre público).
       *  `value` queda crudo para filtros. */
      value_display?: string;
      tipo: string;
      unidad: string | null;
      prioridad: number;
      en_card: boolean;
      en_filtros: boolean;
      destacado: boolean;
    }
  >;
  /** Unidades disponibles para el rango desde/hasta. Solo presente si se pasan fechas. */
  disponible?: number;
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

/* ─── Endpoints ─────────────────────────────────────────────────────── */

export function apiGetEquipos(opts?: { desde?: string; hasta?: string }) {
  return get<{ total: number; items: BackendEquipo[] }>("/api/equipos", {
    per_page: "500",
    solo_visibles: "true",
    sort: "ranking",
    ...(opts?.desde && opts?.hasta ? { desde: opts.desde, hasta: opts.hasta } : {}),
  });
}

export function apiGetCategorias() {
  return get<BackendCategoria[]>("/api/categorias");
}

/** Días (YYYY-MM-DD) sin disponibilidad para los equipos del carrito, en el
 *  rango pedido. `items` = "equipo_id:cantidad" separado por coma. */
export function apiGetDiasBloqueados(items: string, desde: string, hasta: string) {
  return get<{ dias_bloqueados: string[] }>("/api/disponibilidad-dias", {
    items,
    desde,
    hasta,
  });
}

export type DescuentoJornada = { id: number; jornadas: number; pct: number };

export function apiGetDescuentosJornada() {
  return get<DescuentoJornada[]>("/api/descuentos-jornada");
}

export function interpolarDescuento(puntos: DescuentoJornada[], jornadas: number): number {
  if (!puntos.length) return 0;
  const sorted = [...puntos].sort((a, b) => a.jornadas - b.jornadas);
  if (jornadas <= sorted[0].jornadas) return sorted[0].pct;
  if (jornadas >= sorted[sorted.length - 1].jornadas) return sorted[sorted.length - 1].pct;
  for (let i = 0; i < sorted.length - 1; i++) {
    const { jornadas: j0, pct: p0 } = sorted[i];
    const { jornadas: j1, pct: p1 } = sorted[i + 1];
    if (jornadas >= j0 && jornadas <= j1) {
      const t = (jornadas - j0) / (j1 - j0);
      return Math.round((p0 + t * (p1 - p0)) * 10) / 10;
    }
  }
  return 0;
}

export function apiGetMarcs() {
  return get<{ items: BackendMarca[] }>("/api/marcas");
}

// NOTA: la creación de pedidos se movió a `src/lib/orders.ts → createOrder()`
// usando el endpoint autenticado /api/cliente/pedidos del backend FastAPI.
