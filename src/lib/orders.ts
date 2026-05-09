/**
 * orders.ts — API de pedidos del cliente.
 *
 * Habla con el backend FastAPI (Railway) usando el JWT de Supabase Auth.
 * El backend valida el JWT, hace upsert del cliente y crea/lee `alquileres`.
 * Antes esto vivía duplicado en una tabla `orders` de Supabase; ya no.
 */

import { authedJson, authedPostJson, authedFetch } from "./authedFetch";

export type OrderStatus =
  | "borrador"
  | "solicitado"
  | "confirmado"
  | "entregado"
  | "devuelto"
  | "cancelado";

export const STATUS_LABEL: Record<OrderStatus, string> = {
  borrador: "Borrador",
  solicitado: "Solicitado",
  confirmado: "Confirmado",
  entregado: "Entregado",
  devuelto: "Devuelto",
  cancelado: "Cancelado",
};

export const STATUS_TONE: Record<OrderStatus, string> = {
  borrador: "bg-muted text-muted-foreground",
  solicitado: "bg-amber/20 text-ink",
  confirmado: "bg-green-500/15 text-green-700",
  entregado: "bg-blue-500/15 text-blue-700",
  devuelto: "bg-foreground text-background",
  cancelado: "bg-destructive/10 text-destructive",
};

export function isEditable(status: OrderStatus) {
  return status === "borrador" || status === "solicitado";
}

export type OrderItemInput = {
  id: string;
  name: string;
  brand: string;
  category: string;
  qty: number;
  pricePerDay: number;
  /** ID numérico del equipo en el backend FastAPI. Requerido para crear pedido. */
  backendId?: number;
};

export type CreateOrderInput = {
  status: OrderStatus;
  startDate?: Date;
  endDate?: Date;
  startTime: string;
  endTime: string;
  days: number;
  resolvedItems: OrderItemInput[];
  notes?: string;
};

export type Order = {
  id: string;
  status: OrderStatus;
  start_date: string | null;
  end_date: string | null;
  start_time: string;
  end_time: string;
  days: number;
  total: number;
  notes: string | null;
};

export type OrderItem = {
  id: string;
  name: string;
  brand: string;
  qty: number;
  price_per_day: number;
};

export type ChangeRequest = {
  id: string;
  status: "pendiente" | "aceptado" | "rechazado";
  message: string;
  created_at: string;
};

/* ── Mapeo backend → frontend ─────────────────────────────────────────────── */

const ESTADO_MAP: Record<string, OrderStatus> = {
  borrador: "borrador",
  presupuesto: "solicitado",
  solicitado: "solicitado",
  confirmado: "confirmado",
  entregado: "entregado",
  devuelto: "devuelto",
  cancelado: "cancelado",
  finalizado: "devuelto",
};

function pad(n: number) {
  return String(n).padStart(2, "0");
}

function fmtIsoLocal(d: Date, time: string) {
  const y = d.getFullYear();
  return `${y}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${time}:00`;
}

function timePart(d: Date | null, fallback: string) {
  if (!d || isNaN(d.getTime())) return fallback;
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function adaptOrder(b: Record<string, unknown>): Order {
  const fd = b.fecha_desde ? new Date(String(b.fecha_desde)) : null;
  const fh = b.fecha_hasta ? new Date(String(b.fecha_hasta)) : null;
  const days =
    fd && fh
      ? Math.max(1, Math.ceil((fh.getTime() - fd.getTime()) / 86_400_000))
      : 1;
  return {
    id: String(b.id),
    status: ESTADO_MAP[String(b.estado)] ?? "solicitado",
    start_date: fd ? fd.toISOString() : null,
    end_date: fh ? fh.toISOString() : null,
    start_time: timePart(fd, "09:00"),
    end_time: timePart(fh, "18:00"),
    days,
    total: Number(b.monto_total ?? 0),
    notes: (b.notas as string | null) ?? null,
  };
}

function adaptItems(items: Array<Record<string, unknown>>): OrderItem[] {
  return items.map((it, i) => ({
    id: String(it.equipo_id ?? i),
    name: String(it.nombre ?? ""),
    brand: String(it.marca ?? ""),
    qty: Number(it.cantidad ?? 0),
    price_per_day: Number(it.precio_jornada ?? 0),
  }));
}

const SOLIC_MAP: Record<string, ChangeRequest["status"]> = {
  pendiente: "pendiente",
  aprobada: "aceptado",
  rechazada: "rechazado",
};

function adaptChangeRequests(
  arr: Array<Record<string, unknown>>,
): ChangeRequest[] {
  return arr.map((s) => ({
    id: String(s.id),
    status: SOLIC_MAP[String(s.estado)] ?? "pendiente",
    message: String(s.mensaje ?? ""),
    created_at: String(s.created_at ?? new Date().toISOString()),
  }));
}

/* ── API pública ──────────────────────────────────────────────────────────── */

export async function createOrder(input: CreateOrderInput): Promise<Order> {
  const items = (input.resolvedItems ?? []).filter((it) => it.qty > 0);
  if (items.length === 0) throw new Error("El pedido está vacío.");

  const missing = items.find((it) => !it.backendId);
  if (missing) {
    throw new Error(
      `No se puede solicitar "${missing.name}" porque el catálogo está en modo offline.`,
    );
  }

  const body = {
    fecha_desde: input.startDate
      ? fmtIsoLocal(input.startDate, input.startTime)
      : null,
    fecha_hasta: input.endDate ? fmtIsoLocal(input.endDate, input.endTime) : null,
    notas: input.notes ?? null,
    items: items.map((it) => ({
      equipo_id: it.backendId!,
      cantidad: it.qty,
      precio_jornada: Math.round(it.pricePerDay),
    })),
  };

  const created = await authedPostJson<Record<string, unknown>>(
    "/api/cliente/pedidos",
    body,
  );
  return adaptOrder(created);
}

export async function listOrders(): Promise<Order[]> {
  const arr = await authedJson<Array<Record<string, unknown>>>(
    "/api/cliente/pedidos",
  );
  return arr.map(adaptOrder);
}

export async function getOrder(id: string) {
  const b = await authedJson<Record<string, unknown>>(
    `/api/cliente/pedidos/${id}`,
  );
  return {
    order: adaptOrder(b),
    items: adaptItems((b.items as Array<Record<string, unknown>>) ?? []),
    changeRequests: adaptChangeRequests(
      (b.solicitudes as Array<Record<string, unknown>>) ?? [],
    ),
  };
}

export async function cancelOrder(id: string): Promise<void> {
  const res = await authedFetch(`/api/cliente/pedidos/${id}/cancelar`, {
    method: "PATCH",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail ?? `PATCH cancelar → ${res.status}`);
  }
}

export async function createChangeRequest(orderId: string, message: string) {
  await authedPostJson(
    `/api/cliente/pedidos/${orderId}/solicitar-modificacion`,
    { mensaje: message },
  );
}
