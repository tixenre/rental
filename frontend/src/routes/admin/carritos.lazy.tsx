import { createLazyFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { es } from "date-fns/locale";
import {
  ShoppingCart,
  User,
  Package,
  Clock,
  MessageCircle,
  DollarSign,
  TrendingUp,
  Users,
  AlertTriangle,
} from "lucide-react";

import { adminApi } from "@/lib/admin/api";
import type { Carrito } from "@/lib/admin/api/carritos";
import { useDocumentTitle } from "@/lib/use-document-title";
import { fmtArs, formatFechaCorta } from "@/lib/format";
import { whatsappLink } from "@/lib/whatsapp";
import { cn } from "@/lib/utils";
import { Pill } from "@/design-system/kit/Pill";
import { Kpi, Section, BarChart, RankList } from "@/components/admin/LiquidacionReporte";

export const Route = createLazyFileRoute("/admin/carritos")({
  component: CarritosPage,
});

type Filtro = "todos" | "identificados" | "anonimos";
type Orden = "actividad" | "monto";

// Un carrito tocado en los últimos 30 min está "activo ahora".
const FRESCO_MS = 30 * 60 * 1000;

function CarritosPage() {
  useDocumentTitle("Carritos activos · Back Office");

  const { data, isLoading, isError, error, dataUpdatedAt } = useQuery({
    queryKey: ["admin", "carritos"],
    queryFn: () => adminApi.listCarritos(),
    refetchInterval: 30_000,
    staleTime: 10_000,
  });

  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [orden, setOrden] = useState<Orden>("actividad");

  const carritos = useMemo(() => data?.carritos ?? [], [data]);
  const stats = data?.stats;
  const demanda = data?.demanda ?? [];
  const porDia = data?.por_dia ?? [];

  const visibles = useMemo(() => {
    const filtrados = carritos.filter((c) =>
      filtro === "identificados" ? !!c.cliente_id : filtro === "anonimos" ? !c.cliente_id : true,
    );
    return [...filtrados].sort((a, b) =>
      orden === "monto"
        ? b.monto_estimado - a.monto_estimado
        : new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    );
  }, [carritos, filtro, orden]);

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-6xl mx-auto">
      <header>
        <div className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
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
                isLoading ? "bg-amber animate-pulse" : "bg-verde",
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

      {/* KPIs del funnel */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Kpi icon={ShoppingCart} label="Carritos activos" value={String(stats.activos)} />
          <Kpi
            icon={DollarSign}
            label="En juego"
            value={fmtArs(stats.pipeline_ars)}
            sub="Pipeline estimado"
          />
          <Kpi
            icon={TrendingUp}
            label="Conversión 7d"
            value={`${stats.conversion_pct}%`}
            sub={`${stats.confirmados_7d}/${stats.creados_7d} confirmados`}
          />
          <Kpi
            icon={Users}
            label="Identificados"
            value={String(stats.identificados)}
            sub={`${stats.anonimos} anónimos`}
          />
        </div>
      )}

      {/* Alertas accionables */}
      {stats && stats.abandonados > 0 && (
        <div className="flex items-center gap-2 rounded-md border hairline border-amber/40 bg-amber/10 px-3 py-2 text-sm text-ink">
          <Clock className="h-4 w-4 shrink-0" />
          {stats.abandonados} carrito{stats.abandonados !== 1 ? "s" : ""} abandonado
          {stats.abandonados !== 1 ? "s" : ""} (sin actividad hace +24h) — buena oportunidad para
          recuperarlos por WhatsApp.
        </div>
      )}
      {/* Insights: demanda + serie por día */}
      {(demanda.length > 0 || porDia.length > 0) && (
        <div className="grid lg:grid-cols-2 gap-6">
          {demanda.length > 0 && (
            <Section title="Interés latente" subtitle="Equipos más presentes en carritos activos">
              <RankList
                items={demanda.map((d) => ({
                  primary: d.nombre,
                  secondary: `en ${d.carritos} carrito${d.carritos !== 1 ? "s" : ""}`,
                  value: `${d.unidades}u`,
                }))}
                icon={Package}
              />
            </Section>
          )}
          {porDia.length > 0 && (
            <Section title="Carritos por día" subtitle="Creados · últimos 14 días">
              <BarChart
                data={porDia.map((d) => ({ label: d.dia, value: d.creados }))}
                labelFn={(l) => l.slice(8)}
                valueFormat={(n) => String(n)}
              />
            </Section>
          )}
        </div>
      )}

      {/* Toolbar: filtro + orden */}
      {carritos.length > 0 && (
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-1">
            {(
              [
                ["todos", "Todos"],
                ["identificados", "Identificados"],
                ["anonimos", "Anónimos"],
              ] as [Filtro, string][]
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setFiltro(key)}
                className={cn(
                  "h-11 rounded-full border hairline px-3 text-xs font-medium transition",
                  filtro === key
                    ? "bg-ink text-background border-ink"
                    : "text-muted-foreground hover:text-ink",
                )}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1">
            {(
              [
                ["actividad", "Última actividad"],
                ["monto", "Monto"],
              ] as [Orden, string][]
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setOrden(key)}
                className={cn(
                  "h-11 rounded-full border hairline px-3 text-xs font-medium transition",
                  orden === key
                    ? "bg-ink text-background border-ink"
                    : "text-muted-foreground hover:text-ink",
                )}
              >
                {label}
              </button>
            ))}
          </div>
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

      {visibles.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {visibles.map((c) => (
            <CarritoCard key={c.id} carrito={c} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Mensaje de WhatsApp pre-armado y contextual para recuperar el carrito. */
function buildWhatsappMessage(c: Carrito): string {
  const nombre = c.cliente_nombre?.trim().split(/\s+/)[0];
  const saludo = nombre ? `Hola ${nombre}` : "Hola";
  const equipos = c.items
    .map((it) => (it.cantidad > 1 ? `${it.cantidad}× ${it.nombre}` : it.nombre))
    .join(", ");
  const fechas =
    c.fecha_desde && c.fecha_hasta
      ? ` para el ${formatFechaCorta(c.fecha_desde)} al ${formatFechaCorta(c.fecha_hasta)}`
      : "";
  const detalle = equipos ? ` con ${equipos}${fechas}` : "";
  return `${saludo}, te escribo de Rambla Rental 👋 Vi que estás armando un pedido${detalle}. ¿Te doy una mano para confirmarlo?`;
}

function CarritoCard({ carrito: c }: { carrito: Carrito }) {
  const wasaLink = whatsappLink({ phone: c.cliente_telefono, message: buildWhatsappMessage(c) });
  const tieneCliente = !!c.cliente_id;
  const updatedMs = new Date(c.updated_at).getTime();
  const activoAhora = Date.now() - updatedMs < FRESCO_MS;
  const ultimaActividad = formatDistanceToNow(updatedMs, { addSuffix: true, locale: es });

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
              className="flex h-11 w-11 items-center justify-center rounded-full text-verde hover:bg-verde/10 transition"
              title="Escribir por WhatsApp"
            >
              <MessageCircle className="h-4 w-4" />
            </a>
          )}
        </div>
      </div>

      {/* Badges de estado */}
      <div className="flex flex-wrap items-center gap-1.5">
        {activoAhora && <Pill tone="success">Activo ahora</Pill>}
        {c.abandonado && <Pill tone="warning">Abandonado</Pill>}
        {c.sin_stock && (
          <Pill tone="danger">
            <AlertTriangle className="mr-1 h-3 w-3" />
            Sin stock para esas fechas
          </Pill>
        )}
      </div>

      {/* Items */}
      <div className="space-y-1">
        {c.items.map((it) => {
          const itemSinStock = typeof it.disponible === "number" && it.cantidad > it.disponible;
          return (
            <div key={it.equipo_id} className="flex items-center gap-2 text-sm">
              <Package
                className={cn(
                  "h-3.5 w-3.5 shrink-0",
                  itemSinStock ? "text-destructive" : "text-muted-foreground",
                )}
              />
              <span className={cn("truncate", itemSinStock ? "text-destructive" : "text-ink")}>
                {it.nombre}
              </span>
              <span className="ml-auto shrink-0 font-mono text-xs text-muted-foreground">
                ×{it.cantidad}
              </span>
            </div>
          );
        })}
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
