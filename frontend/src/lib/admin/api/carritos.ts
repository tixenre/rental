import { authedJson } from "@/lib/authedFetch";

export type CarritoItem = {
  equipo_id: number;
  cantidad: number;
  nombre: string;
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
  created_at: string;
  updated_at: string;
};

type CarritosResp = {
  carritos: Carrito[];
  total: number;
};

export const carritosMethods = {
  listCarritos: (horas = 72) => authedJson<CarritosResp>(`/api/admin/carritos?horas=${horas}`),
};
