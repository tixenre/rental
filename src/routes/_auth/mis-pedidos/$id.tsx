import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Send, X, FileText, Download, ExternalLink, Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  getOrder,
  cancelOrder,
  createChangeRequest,
  isEditable,
  STATUS_LABEL,
  STATUS_TONE,
  DOCUMENTO_LABEL,
  DOCUMENTO_HINT,
  openOrderDocument,
  downloadOrderDocument,
  type OrderStatus,
  type DocumentoTipo,
} from "@/lib/orders";
import { format } from "date-fns";
import { es } from "date-fns/locale";

export const Route = createFileRoute("/_auth/mis-pedidos/$id")({
  head: () => ({
    meta: [{ title: "Detalle del pedido — Rambla Rental" }],
  }),
  component: OrderDetailPage,
});

function OrderDetailPage() {
  const { id } = Route.useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [message, setMessage] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["order", id],
    queryFn: () => getOrder(id),
  });

  const cancelMut = useMutation({
    mutationFn: () => cancelOrder(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["order", id] }),
  });

  const requestMut = useMutation({
    mutationFn: (msg: string) => createChangeRequest(id, msg),
    onSuccess: () => {
      setMessage("");
      qc.invalidateQueries({ queryKey: ["order", id] });
    },
  });

  if (isLoading || !data) {
    return <div className="grid min-h-screen place-items-center text-sm text-muted-foreground">Cargando…</div>;
  }

  const { order, items, changeRequests, documentosDisponibles } = data;
  const status = order.status as OrderStatus;
  const editable = isEditable(status);

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b hairline px-4 py-4 md:px-8">
        <button
          onClick={() => navigate({ to: "/mis-pedidos" })}
          className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-ink"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Mis pedidos
        </button>
      </div>

      <div className="mx-auto max-w-3xl px-4 py-8 md:px-8 space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Pedido #{order.id.slice(0, 8)}
            </div>
            <h1 className="font-display text-3xl text-ink">
              {order.start_date && order.end_date
                ? `${format(new Date(order.start_date), "dd MMM", { locale: es })} → ${format(
                    new Date(order.end_date),
                    "dd MMM yyyy",
                    { locale: es },
                  )}`
                : "Sin fechas"}
            </h1>
            <div className="mt-2 text-xs text-muted-foreground">
              {order.days} {order.days === 1 ? "jornada" : "jornadas"} · {order.start_time} → {order.end_time}
            </div>
          </div>
          <span
            className={
              "rounded-full px-3 py-1 text-[11px] font-mono uppercase tracking-widest " +
              STATUS_TONE[status]
            }
          >
            {STATUS_LABEL[status]}
          </span>
        </div>

        <div className="rounded-xl border hairline bg-surface">
          <div className="border-b hairline px-4 py-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            Equipos
          </div>
          <ul className="divide-y hairline">
            {items.map((it) => (
              <li key={it.id} className="flex items-center justify-between gap-4 px-4 py-3">
                <div className="min-w-0">
                  <div className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                    {it.brand}
                  </div>
                  <div className="truncate text-sm text-ink">{it.name}</div>
                </div>
                <div className="text-right">
                  <div className="text-xs tabular text-muted-foreground">×{it.qty}</div>
                  <div className="text-sm tabular text-ink">
                    ${Number(it.price_per_day).toLocaleString("es-AR")}/día
                  </div>
                </div>
              </li>
            ))}
          </ul>
          <div className="border-t hairline px-4 py-3 flex items-center justify-between">
            <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Total
            </span>
            <span className="font-display text-2xl tabular text-ink">
              ${Number(order.total).toLocaleString("es-AR")}
            </span>
          </div>
        </div>

        {/* Cambios / cancelación */}
        {status !== "cancelado" && status !== "devuelto" && (
          <div className="rounded-xl border hairline bg-surface p-4 space-y-3">
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Solicitar un cambio
            </div>
            <p className="text-xs text-muted-foreground">
              {editable
                ? "Tu pedido aún no está confirmado. Igual podés enviarnos una solicitud para que registremos la modificación."
                : "Tu pedido ya está confirmado. Enviá una solicitud y la revisamos antes de aplicarla."}
            </p>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Ej: cambiar la lente 50mm por una 35mm, sumar un día más, etc."
              rows={3}
              maxLength={500}
              className="w-full resize-none rounded-md border hairline bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber"
            />
            <div className="flex items-center justify-between">
              <button
                onClick={() => cancelMut.mutate()}
                disabled={cancelMut.isPending || !editable}
                className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-destructive disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <X className="h-3.5 w-3.5" /> Cancelar pedido
              </button>
              <button
                onClick={() => requestMut.mutate(message)}
                disabled={!message.trim() || requestMut.isPending}
                className="inline-flex items-center gap-2 rounded-md bg-amber px-3 py-2 text-xs font-medium uppercase tracking-widest text-ink hover:brightness-110 disabled:opacity-40"
              >
                <Send className="h-3.5 w-3.5" />
                Enviar solicitud
              </button>
            </div>
          </div>
        )}

        {changeRequests.length > 0 && (
          <div className="rounded-xl border hairline bg-surface">
            <div className="border-b hairline px-4 py-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Solicitudes de cambio
            </div>
            <ul className="divide-y hairline">
              {changeRequests.map((cr) => (
                <li key={cr.id} className="px-4 py-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
                      {format(new Date(cr.created_at), "dd MMM yyyy HH:mm", { locale: es })}
                    </span>
                    <span
                      className={
                        "rounded-full px-2 py-0.5 text-[10px] font-mono uppercase tracking-widest " +
                        (cr.status === "pendiente"
                          ? "bg-amber/20 text-ink"
                          : cr.status === "aceptado"
                            ? "bg-green-500/15 text-green-700"
                            : "bg-destructive/10 text-destructive")
                      }
                    >
                      {cr.status}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-ink whitespace-pre-wrap">{cr.message}</p>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
