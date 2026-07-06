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
import { Receipt } from "lucide-react";

import { adminApi, DESTINATARIOS_PAGO, METODOS_PAGO } from "@/lib/admin/api";
import { formatARS, formatFechaDisplay } from "@/lib/format";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { Badge } from "@/design-system/ui/badge";
import { Input } from "@/design-system/ui/input";
import { FieldLabel } from "@/design-system/ui/Field";
import { AdminPage } from "@/components/admin/AdminPage";
import { AdminTable, type Column } from "@/components/admin/AdminTable";
import { QueryState } from "@/components/admin/QueryState";
import { TableSkeleton } from "@/components/admin/skeletons";
import { EmptyState } from "@/design-system/composites/EmptyState";
import { SegmentedControl } from "@/design-system/ui/segmented-control";

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

  const columns: Column<(typeof pagos)[number]>[] = [
    {
      header: "Fecha",
      cell: (p) => formatFechaDisplay(p.fecha),
      className: "whitespace-nowrap text-muted-foreground",
    },
    {
      header: "Pedido",
      cell: (p) => (
        <Link
          to="/admin/pedidos/$id"
          params={{ id: String(p.pedido_id) }}
          className="text-ink underline decoration-amber/60 underline-offset-2 hover:decoration-amber font-mono"
        >
          #{p.numero_pedido ?? p.pedido_id}
        </Link>
      ),
      className: "whitespace-nowrap",
    },
    {
      header: "Cliente",
      cell: (p) => p.cliente_nombre ?? "—",
      className: "max-w-[180px] truncate",
    },
    {
      header: "Concepto",
      cell: (p) => p.concepto ?? "—",
      className: "text-muted-foreground",
    },
    {
      header: "Cobró",
      cell: (p) =>
        p.destinatario ? (
          <Badge variant="secondary" className="capitalize">
            {p.destinatario}
          </Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
      className: "whitespace-nowrap",
    },
    {
      header: "Método",
      cell: (p) => p.metodo ?? "—",
      className: "whitespace-nowrap capitalize text-muted-foreground",
    },
    {
      header: "Monto",
      cell: (p) => formatARS(p.monto),
      align: "right",
      className: "font-mono tabular-nums",
    },
  ];

  return (
    <AdminPage
      title="Cobros de pedidos"
      eyebrow="Finanzas"
      backTo={{ to: "/admin/contabilidad/movimientos", label: "Movimientos" }}
      maxW="max-w-5xl"
      description={
        <>
          Registro de todos los cobros de pedidos (la fuente única de "pagado"). Cada cobro lleva a
          quién se cobró y el método. El resumen por mes también aparece en Movimientos.
        </>
      }
    >
      <div className="space-y-6">
        {/* Filtros */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <FieldLabel>Destinatario</FieldLabel>
            <SegmentedControl
              value={destinatario}
              onChange={setDestinatario}
              options={[
                { value: "", label: "Todos" },
                ...DESTINATARIOS_PAGO.map((d) => ({ value: d, label: d })),
              ]}
            />
          </div>
          <div className="space-y-1">
            <FieldLabel>Método</FieldLabel>
            <SegmentedControl
              value={metodo}
              onChange={setMetodo}
              options={[
                { value: "", label: "Todos" },
                ...METODOS_PAGO.map((m) => ({ value: m, label: m })),
              ]}
            />
          </div>
          <div className="space-y-1">
            <FieldLabel>Desde</FieldLabel>
            <Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
          </div>
          <div className="space-y-1">
            <FieldLabel>Hasta</FieldLabel>
            <Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
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
          <span className="t-eyebrow">Total {q.data ? `(${q.data.count})` : ""}</span>
          <span className="font-mono text-xl font-semibold tabular-nums text-ink">
            {formatARS(total)}
          </span>
        </div>

        <QueryState
          query={q}
          isEmpty={(d) => (d.pagos ?? []).length === 0}
          skeleton={<TableSkeleton rows={6} cols={7} />}
          empty={
            <EmptyState
              icon={<Receipt className="h-6 w-6" />}
              title="No hay pagos"
              sub="No hay pagos para los filtros elegidos."
            />
          }
        >
          {() => <AdminTable columns={columns} rows={pagos} getRowKey={(p) => p.id} />}
        </QueryState>
      </div>
    </AdminPage>
  );
}
