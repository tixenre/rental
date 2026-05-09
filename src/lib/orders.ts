import { supabase } from "@/integrations/supabase/client";
import { equipment } from "@/data/equipment";

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
};

export type CreateOrderInput = {
  status: OrderStatus;
  startDate?: Date;
  endDate?: Date;
  startTime: string;
  endTime: string;
  days: number;
  /** Mapa id→qty (compat con flujo viejo basado en mock estático). */
  items?: Record<string, number>;
  /** Items enriquecidos (preferido — funciona con backend o mock). */
  resolvedItems?: OrderItemInput[];
  notes?: string;
};

function toIsoDate(d?: Date) {
  if (!d) return null;
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export async function createOrder(input: CreateOrderInput) {
  const { data: u } = await supabase.auth.getUser();
  if (!u.user) throw new Error("Necesitás iniciar sesión.");

  let itemsList: OrderItemInput[];
  if (input.resolvedItems && input.resolvedItems.length > 0) {
    itemsList = input.resolvedItems;
  } else {
    itemsList = Object.entries(input.items ?? {})
      .map(([id, qty]) => {
        const eq = equipment.find((e) => e.id === id);
        if (!eq || qty <= 0) return null;
        return {
          id: eq.id,
          name: eq.name,
          brand: eq.brand,
          category: eq.category,
          qty,
          pricePerDay: eq.pricePerDay,
        };
      })
      .filter(Boolean) as OrderItemInput[];
  }

  const subtotalPerDay = itemsList.reduce((s, it) => s + it.pricePerDay * it.qty, 0);
  const total = subtotalPerDay * input.days;

  const { data: order, error } = await supabase
    .from("orders")
    .insert({
      user_id: u.user.id,
      status: input.status,
      start_date: toIsoDate(input.startDate),
      end_date: toIsoDate(input.endDate),
      start_time: input.startTime,
      end_time: input.endTime,
      days: input.days,
      subtotal_per_day: subtotalPerDay,
      total,
      notes: input.notes ?? null,
    })
    .select()
    .single();
  if (error) throw error;

  if (itemsList.length > 0) {
    const { error: itemsError } = await supabase.from("order_items").insert(
      itemsList.map((it) => ({
        order_id: order.id,
        equipment_id: it.id,
        name: it.name,
        brand: it.brand,
        category: it.category,
        qty: it.qty,
        price_per_day: it.pricePerDay,
      }))
    );
    if (itemsError) throw itemsError;
  }

  return order;
}

export async function listOrders() {
  const { data, error } = await supabase
    .from("orders")
    .select("*")
    .order("created_at", { ascending: false });
  if (error) throw error;
  return data;
}

export async function getOrder(id: string) {
  const [orderRes, itemsRes, requestsRes] = await Promise.all([
    supabase.from("orders").select("*").eq("id", id).single(),
    supabase.from("order_items").select("*").eq("order_id", id),
    supabase
      .from("order_change_requests")
      .select("*")
      .eq("order_id", id)
      .order("created_at", { ascending: false }),
  ]);
  if (orderRes.error) throw orderRes.error;
  return {
    order: orderRes.data,
    items: itemsRes.data ?? [],
    changeRequests: requestsRes.data ?? [],
  };
}

export async function cancelOrder(id: string) {
  const { error } = await supabase.from("orders").update({ status: "cancelado" }).eq("id", id);
  if (error) throw error;
}

export async function createChangeRequest(orderId: string, message: string) {
  const { data: u } = await supabase.auth.getUser();
  if (!u.user) throw new Error("Necesitás iniciar sesión.");
  const { error } = await supabase.from("order_change_requests").insert({
    order_id: orderId,
    user_id: u.user.id,
    message,
  });
  if (error) throw error;
}
