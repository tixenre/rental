import { createLazyFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  TrendingUp,
  TrendingDown,
  Users,
  Package,
  DollarSign,
  Calendar,
  Calculator,
  Heart,
  Repeat,
  Search,
  SearchX,
  Download,
  ChevronLeft,
  ChevronRight,
  Wallet,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";

import { adminApi } from "@/lib/admin/api";
import type { LiquidacionMes } from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";
import { formatARS } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

export const Route = createLazyFileRoute("/admin/estadisticas")({
  component: EstadisticasPage,
});

const fmtArs = (n: number | null | undefined) => formatARS(n ?? 0);

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
          Métricas del negocio y reportes de liquidación.
        </p>
      </header>

      <Tabs defaultValue="resumen">
        <TabsList>
          <TabsTrigger value="resumen">
            <TrendingUp className="h-3.5 w-3.5 mr-1.5" />
            Resumen
          </TabsTrigger>
          <TabsTrigger value="reportes">
            <Wallet className="h-3.5 w-3.5 mr-1.5" />
            Reportes
          </TabsTrigger>
        </TabsList>

        <TabsContent value="resumen" className="space-y-6 mt-6">
          <p className="text-xs text-muted-foreground">
            Solo se contabilizan pedidos confirmados, retirados y finalizados.
          </p>

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
                <Kpi
                  icon={DollarSign}
                  label="Facturado total"
                  value={fmtArs(data.totales.total_ars)}
                />
                <Kpi
                  icon={Calendar}
                  label="Pedidos"
                  value={String(data.totales.total_pedidos ?? 0)}
                />
                <Kpi
                  icon={Users}
                  label="Clientes"
                  value={String(data.totales.total_clientes ?? 0)}
                />
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
                const pedidosPorCliente = t.total_clientes
                  ? (t.total_pedidos / t.total_clientes).toFixed(1)
                  : "0";
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
                    data={[...data.por_mes]
                      .slice(0, 12)
                      .reverse()
                      .map((m) => ({
                        label: m.mes,
                        value: Number(m.total_ars) || 0,
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
                            c.crecimiento_pct >= 0 ? "text-verde" : "text-destructive"
                          }`}
                        >
                          {c.crecimiento_pct >= 0 ? (
                            <TrendingUp className="h-3 w-3" />
                          ) : (
                            <TrendingDown className="h-3 w-3" />
                          )}
                          {c.crecimiento_pct >= 0 ? "+" : ""}
                          {c.crecimiento_pct}%
                        </span>
                      </div>
                    ))}
                  </div>
                </Section>

                {/* Top equipos */}
                <Section title="Top equipos" subtitle="Por facturación">
                  <RankList
                    items={data.top_equipos.map((e) => ({
                      primary: e.equipo,
                      secondary: `${e.veces}× alquilado`,
                      value: fmtArs(e.total_ars),
                    }))}
                    icon={Package}
                  />
                </Section>

                {/* Top clientes */}
                <Section title="Top clientes" subtitle="Por facturación">
                  <RankList
                    items={data.top_clientes.map((c) => ({
                      primary: c.cliente,
                      secondary: `${c.pedidos} pedidos`,
                      value: fmtArs(c.total_ars),
                    }))}
                    icon={Users}
                  />
                </Section>

                {/* Equipos más guardados como favoritos */}
                {(data.favoritos_equipo?.length ?? 0) > 0 && (
                  <Section
                    title="Equipos más guardados"
                    subtitle="Equipos que los clientes marcan como favoritos"
                  >
                    <RankList
                      items={(data.favoritos_equipo ?? []).map((e) => ({
                        primary: e.equipo,
                        secondary: `${e.clientes_unicos} cliente${e.clientes_unicos !== 1 ? "s" : ""}`,
                        value: `${e.total_favoritos}×`,
                      }))}
                      icon={Heart}
                    />
                  </Section>
                )}

                {/* Recurrentes */}
                <Section title="Clientes recurrentes" subtitle="Más de 1 alquiler">
                  <RankList
                    items={data.clientes_recurrentes.map((c) => ({
                      primary: c.cliente,
                      secondary: `${c.veces_alquiladas}× alquilado`,
                      value: fmtArs(c.total_ars),
                    }))}
                    icon={Users}
                  />
                </Section>

                {/* Por dueño */}
                <Section title="Por dueño" subtitle="Reparto de equipos">
                  <RankList
                    items={data.por_dueno.map((d) => ({
                      primary: d.dueno,
                      secondary: `${d.items} ítems`,
                      value: fmtArs(d.total_ars),
                    }))}
                    icon={Package}
                  />
                </Section>
              </div>
            </>
          )}

          <BusquedasSection />
        </TabsContent>

        <TabsContent value="reportes" className="mt-6">
          <LiquidacionReporte />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function LiquidacionReporte() {
  const pad = (n: number) => String(n).padStart(2, "0");
  const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const [anchor, setAnchor] = useState(() => new Date());
  const [downloading, setDownloading] = useState(false);

  const y = anchor.getFullYear();
  const m = anchor.getMonth();
  const mesDesde = iso(new Date(y, m, 1));
  const mesHasta = iso(new Date(y, m + 1, 0)); // último día del mes
  const anioDesde = iso(new Date(y, 0, 1));
  const anioHasta = iso(new Date(y, 11, 31));

  const mesQ = useQuery({
    queryKey: ["admin", "liquidacion", "mes", mesDesde, mesHasta],
    queryFn: () => adminApi.getLiquidacion(mesDesde, mesHasta),
  });
  const anioQ = useQuery({
    queryKey: ["admin", "liquidacion", "anio", anioDesde, anioHasta],
    queryFn: () => adminApi.getLiquidacion(anioDesde, anioHasta),
  });
  const mes = mesQ.data;
  const anio = anioQ.data;

  const reconQ = useQuery({
    queryKey: ["admin", "liquidacion", "reconciliacion"],
    queryFn: () => adminApi.getReconciliacion(),
  });
  const recon = reconQ.data;

  const mesLabel = new Intl.DateTimeFormat("es-AR", { month: "long", year: "numeric" }).format(
    anchor,
  );
  const beneficiarios = mes?.beneficiarios ?? anio?.beneficiarios ?? [];
  const err = (mesQ.error || anioQ.error) as Error | null;

  const descargarCsv = async () => {
    setDownloading(true);
    try {
      const blob = await adminApi.liquidacionCsv(mesDesde, mesHasta);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `liquidacion_${mesDesde}_a_${mesHasta}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  const shiftMonth = (delta: number) => setAnchor(new Date(y, m + delta, 1));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => shiftMonth(-1)}
            className="rounded-md border hairline p-1.5 text-ink hover:bg-ink/5 transition"
            aria-label="Mes anterior"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="font-display text-lg text-ink capitalize min-w-[9rem] text-center">
            {mesLabel}
          </span>
          <button
            type="button"
            onClick={() => shiftMonth(1)}
            className="rounded-md border hairline p-1.5 text-ink hover:bg-ink/5 transition"
            aria-label="Mes siguiente"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
        <button
          type="button"
          onClick={descargarCsv}
          disabled={downloading}
          className="inline-flex items-center gap-1.5 rounded-md border hairline px-3 py-1.5 text-sm text-ink hover:bg-ink/5 disabled:opacity-50 transition"
        >
          <Download className="h-4 w-4" /> {downloading ? "Generando…" : "Exportar CSV"}
        </button>
      </div>

      <p className="text-xs text-muted-foreground">
        Solo pedidos 100% pagados. Cada pedido cuenta en el mes/día en que quedó saldado. El reparto
        entre dueños se configura en{" "}
        <a href="/admin/settings" className="underline hover:text-ink">
          Ajustes
        </a>
        .
      </p>

      {recon && recon.ok && (
        <div className="flex items-center gap-2 rounded-md border hairline border-verde/30 bg-verde/5 px-3 py-2 text-sm text-verde">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          Datos de liquidación consistentes.
        </div>
      )}
      {recon && !recon.ok && (
        <div className="rounded-md border hairline border-amber/40 bg-amber/5 px-3 py-2 text-sm text-ink space-y-1">
          <div className="flex items-center gap-2 font-medium">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber" />
            Revisá estos datos — pueden afectar los números del reporte:
          </div>
          <ul className="list-disc pl-6 text-xs text-muted-foreground space-y-0.5">
            {recon.pagados_sin_ledger.cantidad > 0 && (
              <li>
                {recon.pagados_sin_ledger.cantidad} pedido(s) marcados pagados pero sin pagos
                registrados (no aparecen en el reporte): #{recon.pagados_sin_ledger.ids.join(", #")}
              </li>
            )}
            {recon.monto_pagado_divergente.cantidad > 0 && (
              <li>
                {recon.monto_pagado_divergente.cantidad} pedido(s) con monto pagado distinto a la
                suma de sus pagos: #{recon.monto_pagado_divergente.ids.join(", #")}
              </li>
            )}
            {recon.sobrepagados.cantidad > 0 && (
              <li>
                {recon.sobrepagados.cantidad} pedido(s) con más cobrado que su total actual (¿lo
                editaste después de cobrar?): #{recon.sobrepagados.ids.join(", #")}
              </li>
            )}
            {recon.duenos_no_canonicos.length > 0 && (
              <li>Dueños fuera del reparto configurado: {recon.duenos_no_canonicos.join(", ")}</li>
            )}
          </ul>
        </div>
      )}

      {err && (
        <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          Error: {err.message}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi icon={DollarSign} label={`Total ${mesLabel}`} value={fmtArs(mes?.resumen.total)} />
        {beneficiarios.map((b) => (
          <Kpi
            key={b}
            icon={Wallet}
            label={b}
            value={fmtArs(mes?.resumen.por_beneficiario[b] ?? 0)}
          />
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <Section title="Día a día" subtitle={`Lo que entró cada día de ${mesLabel}`}>
          <BarChart
            data={(mes?.por_dia ?? []).map((d) => ({ label: d.dia, value: d.total }))}
            labelFn={(l) => l.slice(8)}
          />
        </Section>

        <Section title={`Mes a mes · ${y}`} subtitle="Total y reparto por mes">
          <MesAMesTabla meses={anio?.por_mes ?? []} beneficiarios={beneficiarios} />
        </Section>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {(mes?.por_dueno ?? []).map((d) => (
          <Section
            key={d.dueno}
            title={d.dueno}
            subtitle={`Generó ${fmtArs(d.monto_generado)} · reparte ${beneficiarios
              .filter((b) => d.reparto[b])
              .map((b) => `${b} ${fmtArs(d.reparto[b])}`)
              .join(" · ")}`}
          >
            <RankList
              icon={Package}
              items={d.equipos.map((eq) => ({
                primary: eq.equipo,
                secondary: "generado",
                value: fmtArs(eq.monto),
              }))}
            />
          </Section>
        ))}
        {mes && mes.por_dueno.length === 0 && (
          <div className="text-sm text-muted-foreground">Sin pedidos saldados en {mesLabel}.</div>
        )}
      </div>
    </div>
  );
}

function MesAMesTabla({
  meses,
  beneficiarios,
}: {
  meses: LiquidacionMes[];
  beneficiarios: string[];
}) {
  if (!meses.length) return <div className="text-sm text-muted-foreground">Sin datos</div>;
  const fmtMes = (mes: string) => {
    const [yy, mm] = mes.split("-").map(Number);
    return new Intl.DateTimeFormat("es-AR", { month: "short" }).format(new Date(yy, mm - 1, 1));
  };
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-muted-foreground">
            <th className="text-left font-normal py-1">Mes</th>
            {beneficiarios.map((b) => (
              <th key={b} className="text-right font-normal py-1">
                {b}
              </th>
            ))}
            <th className="text-right font-normal py-1">Total</th>
          </tr>
        </thead>
        <tbody>
          {meses.map((mes) => (
            <tr key={mes.mes} className="border-t hairline">
              <td className="py-1.5 text-ink capitalize">{fmtMes(mes.mes)}</td>
              {beneficiarios.map((b) => (
                <td key={b} className="py-1.5 text-right tabular-nums text-muted-foreground">
                  {fmtArs(mes.por_beneficiario[b] ?? 0)}
                </td>
              ))}
              <td className="py-1.5 text-right tabular-nums text-ink font-medium">
                {fmtArs(mes.total)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const VENTANAS: { label: string; dias?: number }[] = [
  { label: "30 días", dias: 30 },
  { label: "90 días", dias: 90 },
  { label: "Todo" },
];

function BusquedasSection() {
  const [dias, setDias] = useState<number | undefined>(30);
  const q = useQuery({
    queryKey: ["admin", "busquedas", dias ?? "all"],
    queryFn: () => adminApi.getBusquedas(dias),
  });
  const data = q.data;
  const fmtFecha = (s: string | null) => (s ? new Date(s).toLocaleDateString("es-AR") : "—");

  return (
    <section className="space-y-3 border-t hairline pt-6">
      <div className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <h2 className="font-display text-2xl text-ink">Qué busca la gente</h2>
          <p className="text-sm text-muted-foreground">
            Términos del buscador del catálogo. Lo que buscan y da <strong>0 resultados</strong> es
            demanda que todavía no estás cubriendo.
          </p>
        </div>
        <div className="flex gap-1">
          {VENTANAS.map((v) => (
            <button
              key={v.label}
              onClick={() => setDias(v.dias)}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-medium border hairline transition",
                dias === v.dias ? "bg-ink text-background" : "text-muted-foreground hover:text-ink",
              )}
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {q.isLoading && <div className="text-sm text-muted-foreground">Cargando…</div>}
      {q.error && (
        <div className="rounded-md border hairline border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          Error: {(q.error as Error).message}
        </div>
      )}

      {data && (
        <div className="grid gap-4 md:grid-cols-2">
          <Section title="Más buscado" subtitle="Ordenado por cantidad de búsquedas">
            <RankList
              items={data.top.map((r) => ({
                primary: r.texto,
                secondary: `${fmtFecha(r.ultima)} · ${r.max_resultados ?? 0} resultados`,
                value: `${r.veces}×`,
              }))}
              icon={Search}
            />
          </Section>
          <Section title="Buscado sin resultados" subtitle="Demanda no cubierta (0 resultados)">
            <RankList
              items={data.zero.map((r) => ({
                primary: r.texto,
                secondary: `última vez: ${fmtFecha(r.ultima)}`,
                value: `${r.veces}×`,
              }))}
              icon={SearchX}
            />
          </Section>
        </div>
      )}
    </section>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  sub?: string;
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

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border hairline bg-background p-4">
      <h2 className="font-display text-lg text-ink">{title}</h2>
      {subtitle && <p className="text-xs text-muted-foreground mb-3">{subtitle}</p>}
      <div className="mt-2">{children}</div>
    </div>
  );
}

function BarChart({
  data,
  labelFn = (l) => l.slice(5),
}: {
  data: { label: string; value: number }[];
  labelFn?: (label: string) => string;
}) {
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
            {labelFn(d.label)}
          </div>
        </div>
      ))}
    </div>
  );
}

function RankList({
  items,
  icon: Icon,
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
