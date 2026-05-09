/**
 * Admin API client — wrappers tipados de los endpoints del back-office FastAPI.
 *
 * Todos requieren JWT de Supabase con email en ADMIN_EMAILS (validado por
 * `require_admin` en backend/supabase_auth.py).
 */

import { authedJson } from "@/lib/authedFetch";

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

export const adminApi = {
  dashboard: () => authedJson<DashboardData>("/api/dashboard"),
};
