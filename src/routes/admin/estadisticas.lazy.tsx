import { createLazyFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { TrendingUp, TrendingDown, Users, Package, DollarSign, Calendar, Calculator, Heart, Repeat } from "lucide-react";

import { adminApi } from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/estadisticas")({
  component: EstadisticasPage,
});

const fmtArs = (n: number | null | undefined) =>
  n != null ? `$${Math.round(Number(n)).toLocaleString("es-AR")}` : "$0";

function EstadisticasPage() {
  useDocumentTitle("Estadísticas · Back Office");
  const statsQ = useQuery({
    queryKey: ["admin", "estadisticas"],
    queryFn: () => adminApi.getEstadisticas(),
  });

  const data = statsQ.data;

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-7xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office
        </div>
        <h1 className="font-display text-3xl text-ink">Estadísticas</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Solo se contabilizan pedidos confirmados, retirados y finalizados.
        </p>
      </header>

      {statsQ.isLoading && <div className="text-sm text-muted-foreground">Cargando…</div>}
      {statsQ.error && (
        <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          Error: {(statsQ.error as Error).message}
        </div>
      )}

      {data && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Kpi icon={DollarSign} label="Facturado total" value={fmtArs(data.totales.total_ars)} />
            <Kpi icon={Calendar} label="Pedidos" value={String(data.totales.total_pedidos ?? 0)} />
            <Kpi icon={Users} label="Clientes" value={String(data.totales.total_clientes ?? 0)} />
            <Kpi
              icon={TrendingUp}
              label="Mejor mes"
              value={data.mejor_peor_mes.mejor_mes ?? "—"}
              sub={fmtArs(data.mejor_peor_mes.mejor_total)}
            />
          </div>

          {/* KPIs derivados: ticket promedio + LTV. Calculados en frontend
              porque ya tenemos todos los totales — no hace falta backend. */}
          {(() => {
            const t = data.totales;
            const ticket = t.total_pedidos ? Math.round(t.total_ars / t.total_pedidos) : 0;
            const ltv = t.total_clientes ? Math.round(t.total_ars / t.total_clientes) : 0;
            const pedidosPorCliente = t.total_clientes ? (t.total_pedidos / t.total_clientes).toFixed(1) : "0";
            return (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <Kpi
                  icon={Calculator}
                  label="Ticket promedio"
                  value={fmtArs(ticket)}
                  sub="Facturado / Pedidos"
                />
                <Kpi
                  icon={Heart}
                  label="LTV cliente"
                  value={fmtArs(ltv)}
                  sub="Facturado / Clientes"
                />
                <Kpi
                  icon={Repeat}
                  label="Pedidos / cliente"
                  value={pedidosPorCliente}
                  sub="Frecuencia promedio"
                />
              </div>
            );
          })()}

          <div className="grid lg:grid-cols-2 gap-6">
            {/* Por mes (sparkline) */}
            <Section title="Facturación por mes" subtitle="Últimos 24 meses">
              <BarChart
                data={[...data.por_mes].slice(0, 12).reverse().map((m) => ({
                  label: m.mes, value: Number(m.total_ars) || 0,
                }))}
              />
            </Section>

            {/* Crecimiento */}
            <Section title="Crecimiento mes a mes" subtitle="% vs mes anterior">
              <div className="space-y-1.5">
                {data.crecimiento.slice(0, 8).map((c) => (
                  <div key={c.mes} className="flex items-center justify-between text-sm">
                    <span className="font-mono text-xs text-muted-foreground">{c.mes}</span>
                    <span className="tabular-nums text-ink">{fmtArs(c.total_ars)}</span>
                    <span
                      className={`inline-flex items-center gap-1 font-mono text-xs tabular-nums w-20 justify-end ${
                        c.crecimiento_pct >= 0 ? "text-emerald-700" : "text-destructive"
                      }`}
                    >
                      {c.crecimiento_pct >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                      {c.crecimiento_pct >= 0 ? "+" : ""}{c.crecimiento_pct}%
                    </span>
                  </div>
                ))}
              </div>
            </Section>

            {/* Top equipos */}
            <Section title="Top equipos" subtitle="Por facturación">
              <RankList
                items={data.top_equipos.map((e) => ({
                  primary: e.equipo, secondary: `${e.veces}× alquilado`, value: fmtArs(e.total_ars),
                }))}
                icon={Package}
              />
            </Section>

            {/* Top clientes */}
            <Section title="Top clientes" subtitle="Por facturación">
              <RankList
                items={data.top_clientes.map((c) => ({
                  primary: c.cliente, secondary: `${c.pedidos} pedidos`, value: fmtArs(c.total_ars),
                }))}
                icon={Users}
              />
            </Section>

            {/* Recurrentes */}
            <Section title="Clientes recurrentes" subtitle="Más de 1 alquiler">
              <RankList
                items={data.clientes_recurrentes.map((c) => ({
                  primary: c.cliente, secondary: `${c.veces_alquiladas}× alquilado`, value: fmtArs(c.total_ars),
                }))}
                icon={Users}
              />
            </Section>

            {/* Por dueño */}
            <Section title="Por dueño" subtitle="Reparto de equipos">
              <RankList
                items={data.por_dueno.map((d) => ({
                  primary: d.dueno, secondary: `${d.items} ítems`, value: fmtArs(d.total_ars),
                }))}
                icon={Package}
              />
            </Section>
          </div>
        </>
      )}
    </div>
  );
}

function Kpi({
  icon: Icon, label, value, sub,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string; value: string; sub?: string;
}) {
  return (
    <div className="rounded-lg border hairline bg-background p-3">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Icon className="h-4 w-4" />
        <div className="font-mono text-[10px] uppercase tracking-[0.2em]">{label}</div>
      </div>
      <div className="font-display text-2xl text-ink mt-1.5 truncate">{value}</div>
      {sub && <div className="text-xs text-muted-foreground tabular-nums">{sub}</div>}
    </div>
  );
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border hairline bg-background p-4">
      <h2 className="font-display text-lg text-ink">{title}</h2>
      {subtitle && <p className="text-xs text-muted-foreground mb-3">{subtitle}</p>}
      <div className="mt-2">{children}</div>
    </div>
  );
}

function BarChart({ data }: { data: { label: string; value: number }[] }) {
  if (!data.length) return <div className="text-sm text-muted-foreground">Sin datos</div>;
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="flex items-end gap-1 h-32">
      {data.map((d) => (
        <div key={d.label} className="flex-1 flex flex-col items-center gap-1 group">
          <div className="text-[9px] font-mono text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity tabular-nums">
            {fmtArs(d.value)}
          </div>
          <div
            className="w-full bg-ink/80 hover:bg-ink rounded-sm transition-colors min-h-[2px]"
            style={{ height: `${(d.value / max) * 100}%` }}
          />
          <div className="text-[9px] font-mono text-muted-foreground truncate w-full text-center">
            {d.label.slice(5)}
          </div>
        </div>
      ))}
    </div>
  );
}

function RankList({
  items, icon: Icon,
}: {
  items: { primary: string; secondary: string; value: string }[];
  icon: React.ComponentType<{ className?: string }>;
}) {
  if (!items.length) return <div className="text-sm text-muted-foreground">Sin datos</div>;
  return (
    <div className="space-y-1.5">
      {items.map((it, i) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <div className="w-5 font-mono text-xs text-muted-foreground tabular-nums">{i + 1}</div>
          <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-ink truncate">{it.primary}</div>
            <div className="text-xs text-muted-foreground">{it.secondary}</div>
          </div>
          <div className="tabular-nums text-ink">{it.value}</div>
        </div>
      ))}
    </div>
  );
}
