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

export type BackendEquipo = {
  id: number;
  nombre: string;
  marca: string;
  modelo: string | null;
  cantidad: number;
  precio_jornada: number | null;
  precio_usd: number | null;
  foto_url: string | null;
  estado: string;
  visible_catalogo: number;
  etiquetas: string[];
  kit: unknown[];
};

export type BackendCategoria = {
  id?: number;
  nombre: string;
  total: number;
  prioridad?: number;
  subtags?: { nombre: string; total: number }[];
};

export type Disponibilidad = Record<string, number>; // equipo_id (string) → unidades disponibles

/* ─── Endpoints ─────────────────────────────────────────────────────── */

export function apiGetEquipos() {
  return get<{ total: number; items: BackendEquipo[] }>("/api/equipos", {
    per_page: "500",
    solo_visibles: "true",
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

// NOTA: la creación de pedidos se movió a `src/lib/orders.ts → createOrder()`
// usando el endpoint autenticado /api/cliente/pedidos del backend FastAPI.
