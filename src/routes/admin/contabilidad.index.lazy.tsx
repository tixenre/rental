/**
 * contabilidad.index.lazy.tsx — Tablero financiero (#809, Fase 1).
 *
 * Muestra la "plata disponible ahora": total + desglose por caja. Los ingresos
 * por alquiler ya vienen DERIVADOS de los cobros (alquiler_pagos) — no se carga
 * nada a mano. En fases siguientes se suman ganancia neta del mes y rendición.
 */
import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";

import { adminApi, type CuentaSaldo } from "@/lib/admin/api";
import { formatARS, formatMoney } from "@/lib/format";
import { useDocumentTitle } from "@/lib/use-document-title";
import { Badge } from "@/components/ui/badge";

export const Route = createLazyFileRoute("/admin/contabilidad/")({
  component: ContabilidadTablero,
});

function ContabilidadTablero() {
  useDocumentTitle("Finanzas · Back Office");

  const q = useQuery({
    queryKey: ["admin", "contabilidad", "tablero"],
    queryFn: () => adminApi.getTablero(),
  });

  const data = q.data;

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-5xl mx-auto">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office · Finanzas
          </div>
          <h1 className="font-display text-3xl text-ink">Tablero</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Cuánta plata hay y dónde. Los cobros de clientes ya entran solos a la caja de quien los
            cobró.
          </p>
        </div>
        <Link
          to="/admin/contabilidad/cuentas"
          className="shrink-0 h-9 rounded-md border hairline px-3 text-sm flex items-center hover:bg-muted/40"
        >
          Administrar cuentas
        </Link>
      </header>

      {q.isLoading && <div className="text-sm text-muted-foreground">Cargando…</div>}
      {q.isError && (
        <div className="text-sm text-destructive">
          Error cargando el tablero. {(q.error as Error)?.message}
        </div>
      )}

      {data && (
        <>
          {/* KPIs: disponible · ganancia del mes · rendición pendiente */}
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border hairline bg-surface-elevated p-5">
              <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                Plata disponible
              </div>
              <div className="font-mono text-3xl font-semibold tabular-nums text-ink mt-1">
                {formatMoney(data.disponible.totales.ARS ?? 0, "ARS")}
              </div>
              {(data.disponible.totales.USD ?? 0) !== 0 && (
                <div className="font-mono text-lg font-semibold tabular-nums text-ink">
                  {formatMoney(data.disponible.totales.USD, "USD")}
                </div>
              )}
              <div className="text-xs text-muted-foreground mt-1">
                Suma de las cajas · al {data.disponible.as_of}
              </div>
            </div>

            <div className="rounded-xl border hairline bg-surface-elevated p-5">
              <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                Ganancia neta · {data.ganancia_mes.mes}
              </div>
              <div
                className={`font-mono text-3xl font-semibold tabular-nums mt-1 ${
                  data.ganancia_mes.neta >= 0 ? "text-ink" : "text-destructive"
                }`}
              >
                {formatARS(data.ganancia_mes.neta)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Ingresos {formatARS(data.ganancia_mes.ingresos)} − gastos{" "}
                {formatARS(data.ganancia_mes.gastos)}
              </div>
            </div>

            <Link
              to="/admin/contabilidad/rendicion"
              className="rounded-xl border hairline bg-surface-elevated p-5 hover:bg-muted/30 transition"
            >
              <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                Rendición pendiente · {data.rendicion_pendiente.mes}
              </div>
              <div className="font-mono text-3xl font-semibold tabular-nums text-ink mt-1">
                {formatARS(data.rendicion_pendiente.total)}
              </div>
              <div className="text-xs text-amber mt-1">Ver rendición →</div>
            </Link>
          </div>

          {/* Por caja */}
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground mb-2">
              Por caja
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {data.disponible.cuentas.map((c) => (
                <CajaCard key={c.id} cuenta={c} />
              ))}
            </div>
          </div>
        </>
      )}

      <ReconciliacionPanel />
    </div>
  );
}

function ReconciliacionPanel() {
  const q = useQuery({
    queryKey: ["admin", "contabilidad", "reconciliacion"],
    queryFn: () => adminApi.getReconciliacionContable(),
  });
  const r = q.data;
  if (!r) return null;

  const problemas: string[] = [];
  if (r.saldos_negativos.cantidad > 0)
    problemas.push(`${r.saldos_negativos.cantidad} caja(s) con saldo negativo`);
  if (r.pagos_sin_socio.cantidad > 0)
    problemas.push(
      `${r.pagos_sin_socio.cantidad} cobro(s) sin socio asignado (${formatARS(r.pagos_sin_socio.monto)})`,
    );
  if (r.movimientos_cuenta_inactiva.cantidad > 0)
    problemas.push(
      `${r.movimientos_cuenta_inactiva.cantidad} movimiento(s) en cuentas dadas de baja`,
    );
  if (!r.reporte.ok) problemas.push("el reporte de liquidación tiene observaciones");

  return (
    <div
      className={`rounded-lg border p-4 ${
        r.ok ? "hairline bg-muted/10" : "border-destructive/40 bg-destructive/5"
      }`}
    >
      <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground mb-1">
        Reconciliación
      </div>
      {r.ok ? (
        <div className="text-sm text-ink">✓ Todo cuadra.</div>
      ) : (
        <ul className="text-sm text-destructive list-disc pl-5 space-y-0.5">
          {problemas.map((p, i) => (
            <li key={i}>{p}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CajaCard({ cuenta }: { cuenta: CuentaSaldo }) {
  return (
    <div className="rounded-lg border hairline p-4 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-ink">{cuenta.nombre}</span>
        <Badge variant="secondary" className="capitalize">
          {cuenta.tipo}
        </Badge>
      </div>
      <div className="font-mono text-2xl font-semibold tabular-nums text-ink">
        {formatMoney(cuenta.saldo, cuenta.moneda)}
      </div>
      <dl className="text-[11px] text-muted-foreground space-y-0.5">
        {cuenta.saldo_inicial !== 0 && (
          <Row label="Saldo inicial" value={formatMoney(cuenta.saldo_inicial, cuenta.moneda)} />
        )}
        {cuenta.ingresos_alquiler !== 0 && (
          <Row
            label="Cobros de alquiler"
            value={formatMoney(cuenta.ingresos_alquiler, cuenta.moneda)}
          />
        )}
        {cuenta.entradas !== 0 && (
          <Row label="Entradas" value={formatMoney(cuenta.entradas, cuenta.moneda)} />
        )}
        {cuenta.egresos !== 0 && (
          <Row label="Salidas" value={`− ${formatMoney(cuenta.egresos, cuenta.moneda)}`} />
        )}
      </dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt>{label}</dt>
      <dd className="font-mono tabular-nums">{value}</dd>
    </div>
  );
}
