import { authedJson } from "@/lib/authedFetch";

export type CarritoItem = {
  equipo_id: number;
  cantidad: number;
  nombre: string;
  /** Unidades libres para las fechas del carrito (motor de reservas). null = sin fechas. */
  disponible?: number | null;
};

export type Carrito = {
  id: number;
  session_id: string;
  cliente_id: number | null;
  cliente_nombre: string | null;
  cliente_email: string | null;
  cliente_telefono: string | null;
  items: CarritoItem[];
  fecha_desde: string | null;
  fecha_hasta: string | null;
  hora_desde: string | null;
  hora_hasta: string | null;
  total_items: number;
  monto_estimado: number;
  confirmado: boolean;
  /** Sin actividad por más de 24h (estampado en backend). */
  abandonado: boolean;
  /** Algún ítem no tiene stock libre para esas fechas (motor de reservas). */
  sin_stock: boolean;
  created_at: string;
  updated_at: string;
};

export type CarritosStats = {
  activos: number;
  pipeline_ars: number;
  identificados: number;
  anonimos: number;
  abandonados: number;
  creados_7d: number;
  confirmados_7d: number;
  conversion_pct: number;
  equipos_en_disputa: number;
};

export type CarritoDemanda = {
  equipo_id: number;
  nombre: string;
  carritos: number;
  unidades: number;
};

export type CarritoPorDia = {
  dia: string;
  creados: number;
  confirmados: number;
};

export type CarritosResp = {
  carritos: Carrito[];
  total: number;
  stats: CarritosStats;
  demanda: CarritoDemanda[];
  por_dia: CarritoPorDia[];
};

export const carritosMethods = {
  listCarritos: (horas = 72) => authedJson<CarritosResp>(`/api/admin/carritos?horas=${horas}`),
};
