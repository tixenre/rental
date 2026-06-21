import { createLazyFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { es } from "date-fns/locale";
import { ShoppingCart, User, Package, Clock, MessageCircle } from "lucide-react";

import { adminApi } from "@/lib/admin/api";
import type { Carrito } from "@/lib/admin/api/carritos";
import { useDocumentTitle } from "@/lib/use-document-title";
import { fmtArs, formatFechaCorta } from "@/lib/format";
import { whatsappLink } from "@/lib/whatsapp";
import { cn } from "@/lib/utils";

export const Route = createLazyFileRoute("/admin/carritos")({
  component: CarritosPage,
});

function CarritosPage() {
  useDocumentTitle("Carritos activos · Back Office");

  const { data, isLoading, isError, error, dataUpdatedAt } = useQuery({
    queryKey: ["admin", "carritos"],
    queryFn: () => adminApi.listCarritos(),
    refetchInterval: 30_000,
    staleTime: 10_000,
  });

  const carritos = data?.carritos ?? [];

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-5xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Back-office
        </div>
        <div className="flex items-end justify-between gap-3 flex-wrap">
          <div>
            <h1 className="font-display text-3xl text-ink">Carritos activos</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Clientes armando pedidos ahora mismo. Se actualiza cada 30 segundos.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span
              className={cn(
                "inline-block h-2 w-2 rounded-full",
                isLoading ? "bg-amber-400 animate-pulse" : "bg-verde",
              )}
            />
            {dataUpdatedAt
              ? `Actualizado ${formatDistanceToNow(dataUpdatedAt, { addSuffix: true, locale: es })}`
              : "Cargando…"}
          </div>
        </div>
      </header>

      {isLoading && <div className="text-sm text-muted-foreground">Cargando carritos…</div>}

      {isError && (
        <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          Error: {(error as Error).message}
        </div>
      )}

      {!isLoading && !isError && carritos.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 text-center gap-3">
          <ShoppingCart className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-muted-foreground text-sm">
            No hay carritos activos en las últimas 72 horas.
          </p>
        </div>
      )}

      {carritos.length > 0 && (
        <>
          <p className="text-xs text-muted-foreground">
            {carritos.length} carrito{carritos.length !== 1 ? "s" : ""} activo
            {carritos.length !== 1 ? "s" : ""} en las últimas 72 horas.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {carritos.map((c) => (
              <CarritoCard key={c.id} carrito={c} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function CarritoCard({ carrito: c }: { carrito: Carrito }) {
  const wasaLink = whatsappLink({ phone: c.cliente_telefono });
  const tieneCliente = !!c.cliente_id;
  const ultimaActividad = formatDistanceToNow(new Date(c.updated_at), {
    addSuffix: true,
    locale: es,
  });

  return (
    <div className="rounded-xl border hairline bg-card p-4 space-y-3">
      {/* Header: cliente + última actividad */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
              tieneCliente ? "bg-ink text-background" : "bg-muted text-muted-foreground",
            )}
          >
            <User className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink truncate">
              {c.cliente_nombre ?? "Anónimo"}
            </p>
            {c.cliente_email && (
              <p className="text-xs text-muted-foreground truncate">{c.cliente_email}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {wasaLink && (
            <a
              href={wasaLink}
              target="_blank"
              rel="noopener noreferrer"
              className="flex h-8 w-8 items-center justify-center rounded-full text-verde hover:bg-verde/10 transition"
              title="WhatsApp"
            >
              <MessageCircle className="h-4 w-4" />
            </a>
          )}
        </div>
      </div>

      {/* Items */}
      <div className="space-y-1">
        {c.items.map((it) => (
          <div key={it.equipo_id} className="flex items-center gap-2 text-sm">
            <Package className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="truncate text-ink">{it.nombre}</span>
            <span className="ml-auto shrink-0 font-mono text-xs text-muted-foreground">
              ×{it.cantidad}
            </span>
          </div>
        ))}
      </div>

      {/* Fechas + monto */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t hairline pt-3 text-xs text-muted-foreground">
        {c.fecha_desde && c.fecha_hasta ? (
          <span>
            {formatFechaCorta(c.fecha_desde)} → {formatFechaCorta(c.fecha_hasta)}
            {c.hora_desde && c.hora_hasta ? ` · ${c.hora_desde}–${c.hora_hasta}` : ""}
          </span>
        ) : (
          <span className="italic">Sin fechas</span>
        )}
        {c.monto_estimado > 0 && (
          <span className="font-semibold text-ink">~{fmtArs(c.monto_estimado)}</span>
        )}
        <span className="ml-auto flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {ultimaActividad}
        </span>
      </div>
    </div>
  );
}
