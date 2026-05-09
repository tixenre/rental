import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Plus } from "lucide-react";
import { listOrders, STATUS_LABEL, STATUS_TONE, type OrderStatus } from "@/lib/orders";
import { format } from "date-fns";
import { es } from "date-fns/locale";

export const Route = createFileRoute("/_auth/mis-pedidos/")({
  head: () => ({
    meta: [
      { title: "Mis pedidos — Rambla Rental" },
      { name: "description", content: "Historial y estado de tus pedidos." },
    ],
  }),
  component: MisPedidosPage,
});

function MisPedidosPage() {
  const { data: orders, isLoading } = useQuery({ queryKey: ["orders"], queryFn: listOrders });

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b hairline px-4 py-4 md:px-8">
        <Link to="/" className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-ink">
          <ArrowLeft className="h-3.5 w-3.5" /> Catálogo
        </Link>
      </div>

      <div className="mx-auto max-w-3xl px-4 py-8 md:px-8">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Tu historial
            </div>
            <h1 className="font-display text-3xl text-ink">Mis pedidos</h1>
          </div>
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-md bg-amber px-3 py-2 text-xs font-medium uppercase tracking-widest text-ink hover:brightness-110"
          >
            <Plus className="h-3.5 w-3.5" /> Nuevo
          </Link>
        </div>

        <div className="mt-8 space-y-3">
          {isLoading && <div className="text-sm text-muted-foreground">Cargando...</div>}
          {!isLoading && orders?.length === 0 && (
            <div className="rounded-xl border hairline bg-surface p-8 text-center">
              <div className="font-display text-xl text-ink">Todavía no enviaste pedidos</div>
              <p className="mt-2 text-sm text-muted-foreground">
                Armá uno desde el catálogo y aparecerá acá.
              </p>
              <Link
                to="/"
                className="mt-4 inline-flex items-center gap-2 rounded-md bg-amber px-4 py-2 text-sm font-medium text-ink hover:brightness-110"
              >
                Ir al catálogo
              </Link>
            </div>
          )}
          {orders?.map((o) => (
            <Link
              key={o.id}
              to="/mis-pedidos/$id"
              params={{ id: o.id }}
              className="block rounded-xl border hairline bg-surface p-4 hover:border-foreground/40 transition"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    #{o.id.slice(0, 8)}
                  </div>
                  <div className="mt-1 font-display text-lg text-ink truncate">
                    {o.start_date && o.end_date
                      ? `${format(new Date(o.start_date), "dd MMM", { locale: es })} → ${format(
                          new Date(o.end_date),
                          "dd MMM yyyy",
                          { locale: es },
                        )}`
                      : "Sin fechas"}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {o.days} {o.days === 1 ? "jornada" : "jornadas"}
                  </div>
                </div>
                <div className="text-right">
                  <span
                    className={
                      "inline-block rounded-full px-2 py-0.5 text-[10px] font-mono uppercase tracking-widest " +
                      STATUS_TONE[o.status as OrderStatus]
                    }
                  >
                    {STATUS_LABEL[o.status as OrderStatus]}
                  </span>
                  <div className="mt-2 font-display text-xl tabular text-ink">
                    ${Number(o.total).toLocaleString("es-AR")}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
