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
import { formatARS } from "@/lib/format";
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

  const saldos = q.data?.disponible;

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

      {saldos && (
        <>
          {/* Plata disponible (total) */}
          <div className="rounded-xl border hairline bg-surface-elevated p-5">
            <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
              Plata disponible
            </div>
            <div className="font-mono text-4xl font-semibold tabular-nums text-ink mt-1">
              {formatARS(saldos.total_disponible)}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              Suma de todas las cajas · al {saldos.as_of}
            </div>
          </div>

          {/* Por caja */}
          <div className="grid gap-3 sm:grid-cols-2">
            {saldos.cuentas.map((c) => (
              <CajaCard key={c.id} cuenta={c} />
            ))}
          </div>
        </>
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
        {formatARS(cuenta.saldo)}
      </div>
      <dl className="text-[11px] text-muted-foreground space-y-0.5">
        {cuenta.saldo_inicial !== 0 && (
          <Row label="Saldo inicial" value={formatARS(cuenta.saldo_inicial)} />
        )}
        {cuenta.ingresos_alquiler !== 0 && (
          <Row label="Cobros de alquiler" value={formatARS(cuenta.ingresos_alquiler)} />
        )}
        {cuenta.entradas !== 0 && <Row label="Entradas" value={formatARS(cuenta.entradas)} />}
        {cuenta.egresos !== 0 && <Row label="Salidas" value={`− ${formatARS(cuenta.egresos)}`} />}
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
