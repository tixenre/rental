/**
 * pagos.lazy.tsx — Logs de pagos (ledger global del back-office).
 *
 * Vista de solo-lectura sobre `alquiler_pagos`, la fuente única de "pagado"
 * (#722). Lista todos los cobros con su pedido, cliente, destinatario y método,
 * con filtros por destinatario / método / rango de fechas.
 */
import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { adminApi, DESTINATARIOS_PAGO, METODOS_PAGO } from "@/lib/admin/api";
import { formatARS, formatFechaDisplay } from "@/lib/format";
import { useDocumentTitle } from "@/lib/use-document-title";
import { Badge } from "@/design-system/ui/badge";
import { cn } from "@/lib/utils";

export const Route = createLazyFileRoute("/admin/pagos")({
  component: PagosLogPage,
});

function PagosLogPage() {
  useDocumentTitle("Cobros de pedidos · Back Office");

  const [destinatario, setDestinatario] = useState<string>("");
  const [metodo, setMetodo] = useState<string>("");
  const [desde, setDesde] = useState<string>("");
  const [hasta, setHasta] = useState<string>("");

  const q = useQuery({
    queryKey: ["admin", "pagos-log", { destinatario, metodo, desde, hasta }],
    queryFn: () =>
      adminApi.listPagosLog({
        destinatario: destinatario || undefined,
        metodo: metodo || undefined,
        desde: desde || undefined,
        hasta: hasta || undefined,
      }),
  });

  const pagos = q.data?.pagos ?? [];
  const total = q.data?.total ?? 0;

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-5xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Back-office · Finanzas
        </div>
        <h1 className="font-display text-3xl text-ink">Cobros de pedidos</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Registro de todos los cobros de pedidos (la fuente única de "pagado"). Cada cobro lleva a
          quién se cobró y el método. El resumen por mes también aparece en Movimientos.
        </p>
      </header>

      {/* Filtros */}
      <div className="flex flex-wrap items-end gap-3">
        <Segment
          label="Destinatario"
          value={destinatario}
          onChange={setDestinatario}
          options={[["", "Todos"], ...DESTINATARIOS_PAGO.map((d) => [d, d] as [string, string])]}
        />
        <Segment
          label="Método"
          value={metodo}
          onChange={setMetodo}
          options={[["", "Todos"], ...METODOS_PAGO.map((m) => [m, m] as [string, string])]}
        />
        <div className="space-y-1">
          <FieldLabel>Desde</FieldLabel>
          <input
            type="date"
            value={desde}
            onChange={(e) => setDesde(e.target.value)}
            className="h-9 rounded-md border hairline bg-surface-elevated px-2 text-sm"
          />
        </div>
        <div className="space-y-1">
          <FieldLabel>Hasta</FieldLabel>
          <input
            type="date"
            value={hasta}
            onChange={(e) => setHasta(e.target.value)}
            className="h-9 rounded-md border hairline bg-surface-elevated px-2 text-sm"
          />
        </div>
        {(destinatario || metodo || desde || hasta) && (
          <button
            type="button"
            onClick={() => {
              setDestinatario("");
              setMetodo("");
              setDesde("");
              setHasta("");
            }}
            className="h-9 text-xs text-muted-foreground hover:text-ink underline"
          >
            Limpiar
          </button>
        )}
      </div>

      {/* Total del subconjunto */}
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          Total {q.data ? `(${q.data.count})` : ""}
        </span>
        <span className="font-mono text-xl font-semibold tabular-nums text-ink">
          {formatARS(total)}
        </span>
      </div>

      {q.isLoading && <div className="text-sm text-muted-foreground">Cargando pagos…</div>}
      {q.isError && (
        <div className="text-sm text-destructive">
          Error cargando los pagos. {(q.error as Error)?.message}
        </div>
      )}

      {!q.isLoading && !q.isError && pagos.length === 0 && (
        <div className="text-sm text-muted-foreground border rounded-lg p-6 text-center">
          No hay pagos para los filtros elegidos.
        </div>
      )}

      {pagos.length > 0 && (
        <div className="overflow-x-auto rounded-lg border hairline">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b hairline text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-3 py-2 font-medium">Fecha</th>
                <th className="px-3 py-2 font-medium">Pedido</th>
                <th className="px-3 py-2 font-medium">Cliente</th>
                <th className="px-3 py-2 font-medium">Concepto</th>
                <th className="px-3 py-2 font-medium">Cobró</th>
                <th className="px-3 py-2 font-medium">Método</th>
                <th className="px-3 py-2 font-medium text-right">Monto</th>
              </tr>
            </thead>
            <tbody>
              {pagos.map((p) => (
                <tr key={p.id} className="border-b hairline last:border-0 hover:bg-muted/30">
                  <td className="px-3 py-2 whitespace-nowrap text-muted-foreground">
                    {formatFechaDisplay(p.fecha)}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <Link
                      to="/admin/pedidos/$id"
                      params={{ id: String(p.pedido_id) }}
                      className="text-ink underline decoration-amber/60 underline-offset-2 hover:decoration-amber font-mono"
                    >
                      #{p.numero_pedido ?? p.pedido_id}
                    </Link>
                  </td>
                  <td className="px-3 py-2 max-w-[180px] truncate">{p.cliente_nombre ?? "—"}</td>
                  <td className="px-3 py-2 text-muted-foreground">{p.concepto ?? "—"}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {p.destinatario ? (
                      <Badge variant="secondary" className="capitalize">
                        {p.destinatario}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap capitalize text-muted-foreground">
                    {p.metodo ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right font-mono tabular-nums">
                    {formatARS(p.monto)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="block font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
      {children}
    </label>
  );
}

function Segment({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <div className="space-y-1">
      <FieldLabel>{label}</FieldLabel>
      <div className="flex gap-1">
        {options.map(([val, lbl]) => (
          <button
            key={val}
            type="button"
            onClick={() => onChange(val)}
            className={cn(
              "rounded-md border px-2.5 py-1.5 text-xs font-medium capitalize transition",
              value === val
                ? "border-ink bg-ink text-background"
                : "border-muted-foreground/30 text-muted-foreground hover:border-ink hover:text-ink",
            )}
          >
            {lbl}
          </button>
        ))}
      </div>
    </div>
  );
}
