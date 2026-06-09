/**
 * contabilidad.reporte.lazy.tsx — Reporte mensual de Rambla (#809).
 *
 * Todo derivado del motor (endpoint `reporte/{mes}`), sin recalcular en el front:
 * devengado (lo que se ganó) · cobrado (lo que entró) · gastos por categoría ·
 * ganancia neta (devengado − gastos) · cargos/pagos de socios del mes · cuenta
 * corriente al día. Devengado y percibido van separados, nunca sumados.
 */
import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { adminApi, type CuentaSaldo } from "@/lib/admin/api";
import { formatARS } from "@/lib/format";
import { useDocumentTitle } from "@/lib/use-document-title";

export const Route = createLazyFileRoute("/admin/contabilidad/reporte")({
  component: ReporteMensualPage,
});

function mesActual() {
  return new Date().toISOString().slice(0, 7);
}

function ReporteMensualPage() {
  useDocumentTitle("Reporte mensual · Finanzas");
  const [mes, setMes] = useState(mesActual());

  const q = useQuery({
    queryKey: ["admin", "contabilidad", "reporte", mes],
    queryFn: () => adminApi.getReporteMensual(mes),
    enabled: /^\d{4}-\d{2}$/.test(mes),
  });
  const r = q.data;
  const socios = ["Pablo", "Tincho"];

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-4xl mx-auto">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office · Finanzas
          </div>
          <h1 className="font-display text-3xl text-ink">Reporte mensual</h1>
          <p className="text-sm text-muted-foreground mt-1">
            El mes de Rambla, completo: cuánto se ganó, qué entró, los gastos y la deuda con cada
            socio. Todo sale del mismo motor — no hay un peso sumado dos veces.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="month"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            className="h-9 rounded-md border hairline bg-surface-elevated px-2 text-sm"
          />
          <Link
            to="/admin/contabilidad"
            className="shrink-0 h-9 rounded-md border hairline px-3 text-sm flex items-center hover:bg-muted/40"
          >
            ← Tablero
          </Link>
        </div>
      </header>

      {q.isLoading && <div className="text-sm text-muted-foreground">Cargando reporte…</div>}
      {q.isError && (
        <div className="text-sm text-destructive">
          Error cargando el reporte. {(q.error as Error)?.message}
        </div>
      )}

      {r && (
        <>
          {r.cerrado && (
            <div className="rounded-md border border-amber/40 bg-amber/5 px-3 py-2 text-xs text-amber">
              Mes cerrado — los números son la foto congelada.
            </div>
          )}

          {/* KPIs del mes */}
          <div className="grid gap-3 sm:grid-cols-3">
            <Kpi
              label="Se ganó (devengado)"
              value={formatARS(r.devengado.total)}
              sub={`${r.devengado.pedidos} pedido(s) saldado(s)`}
            />
            <Kpi label="Gastos del mes" value={formatARS(r.gastos.total)} />
            <Kpi
              label="Ganancia neta"
              value={formatARS(r.ganancia_neta)}
              tone={r.ganancia_neta >= 0 ? "ink" : "destructive"}
              sub="Se ganó − gastos"
            />
          </div>

          {/* Por socio: devengado vs percibido + movimientos del mes */}
          <Section titulo="Por socio">
            <div className="overflow-x-auto rounded-lg border hairline">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b hairline text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                    <th className="px-3 py-2 font-medium">Socio</th>
                    <th className="px-3 py-2 font-medium text-right">Su parte</th>
                    <th className="px-3 py-2 font-medium text-right">Cobró</th>
                    <th className="px-3 py-2 font-medium text-right">Le cargué</th>
                    <th className="px-3 py-2 font-medium text-right">Me pagó</th>
                  </tr>
                </thead>
                <tbody>
                  {["Pablo", "Tincho", "Rambla"].map((s) => (
                    <tr key={s} className="border-b hairline last:border-0">
                      <td className="px-3 py-2 font-medium text-ink">{s}</td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums">
                        {formatARS(r.devengado.por_socio[s] ?? 0)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums">
                        {formatARS(r.cobrado.por_socio[s] ?? 0)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums text-muted-foreground">
                        {socios.includes(s) ? formatARS(r.socios_mes.cargos[s] ?? 0) : "—"}
                      </td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums text-muted-foreground">
                        {socios.includes(s) ? formatARS(r.socios_mes.pagos[s] ?? 0) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-muted-foreground">
              <strong>Su parte</strong> es lo que se ganó y le toca (devengado).{" "}
              <strong>Cobró</strong> es la plata que entró a su nombre (percibido). Son cosas
              distintas — no se suman. «Le cargué / Me pagó» son los movimientos con su cuenta
              corriente este mes.
            </p>
          </Section>

          {/* Gastos por categoría */}
          <Section titulo="Gastos del mes">
            {r.gastos.por_categoria.length === 0 ? (
              <div className="text-sm text-muted-foreground">No hay gastos cargados este mes.</div>
            ) : (
              <div className="rounded-lg border hairline divide-y divide-[var(--hairline)]">
                {r.gastos.por_categoria.map((g) => (
                  <div key={g.categoria} className="flex items-center justify-between px-3 py-2">
                    <span className="text-sm text-ink">{g.categoria}</span>
                    <span className="font-mono text-sm tabular-nums text-destructive">
                      − {formatARS(g.monto)}
                    </span>
                  </div>
                ))}
                <div className="flex items-center justify-between px-3 py-2 font-medium">
                  <span className="text-sm">Total gastos</span>
                  <span className="font-mono text-sm tabular-nums">
                    {formatARS(r.gastos.total)}
                  </span>
                </div>
              </div>
            )}
          </Section>

          {/* Cuenta corriente al día */}
          <Section titulo="Cuenta corriente de socios (al día de hoy)">
            <div className="grid gap-3 sm:grid-cols-2">
              {r.cuenta_corriente.map((s) => (
                <CuentaCorrienteMini key={s.id} socio={s} />
              ))}
            </div>
          </Section>
        </>
      )}
    </div>
  );
}

function Kpi({
  label,
  value,
  sub,
  tone = "ink",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "ink" | "destructive";
}) {
  return (
    <div className="rounded-xl border hairline bg-surface-elevated p-5">
      <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
        {label}
      </div>
      <div
        className={`font-mono text-3xl font-semibold tabular-nums mt-1 ${
          tone === "destructive" ? "text-destructive" : "text-ink"
        }`}
      >
        {value}
      </div>
      {sub && <div className="text-xs text-muted-foreground mt-1">{sub}</div>}
    </div>
  );
}

function Section({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        {titulo}
      </div>
      {children}
    </section>
  );
}

function CuentaCorrienteMini({ socio }: { socio: CuentaSaldo }) {
  const abs = Math.abs(socio.saldo);
  const frase =
    socio.estado === "deudor"
      ? `${socio.nombre} le debe a Rambla`
      : socio.estado === "acreedor"
        ? `Rambla le debe a ${socio.nombre}`
        : "A mano";
  const color =
    socio.estado === "deudor"
      ? "text-destructive"
      : socio.estado === "acreedor"
        ? "text-verde"
        : "text-ink";
  return (
    <div className="rounded-lg border hairline p-4">
      <div className="font-medium text-ink">{socio.nombre}</div>
      <div className={`font-mono text-2xl font-semibold tabular-nums ${color}`}>
        {formatARS(abs)}
      </div>
      <div className="text-sm text-muted-foreground">{frase}</div>
    </div>
  );
}
