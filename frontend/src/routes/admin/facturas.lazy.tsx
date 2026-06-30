/**
 * facturas.lazy.tsx — Listado global de facturas electrónicas ARCA.
 *
 * Vista de solo-lectura sobre la tabla `facturas`, con filtros por emisor,
 * estado y rango de fechas. Espeja el pattern de pagos.lazy.tsx.
 */
import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { facturacionApi, type FacturaEstado } from "@/lib/admin/api";
import { formatARS, formatFechaDisplay } from "@/lib/format";
import { useDocumentTitle } from "@/lib/use-document-title";
import { FacturaBadge } from "@/components/kit/FacturaBadge";
import { cn } from "@/lib/utils";

export const Route = createLazyFileRoute("/admin/facturas")({
  component: FacturasPage,
});

const ESTADOS_FACTURA: FacturaEstado[] = ["pendiente", "emitida", "error", "anulada"];
const EMISORES = ["pablo", "santini"] as const;

function FacturasPage() {
  useDocumentTitle("Facturas ARCA · Back Office");

  const [emisor, setEmisor] = useState<string>("");
  const [estado, setEstado] = useState<string>("");
  const [desde, setDesde] = useState<string>("");
  const [hasta, setHasta] = useState<string>("");

  const q = useQuery({
    queryKey: ["admin", "facturas-lista", { emisor, estado, desde, hasta }],
    queryFn: () =>
      facturacionApi.listFacturas({
        emisor: emisor || undefined,
        estado: estado || undefined,
        desde: desde || undefined,
        hasta: hasta || undefined,
      }),
  });

  const facturas = q.data?.facturas ?? [];
  const totalImp = q.data?.total_imp_total ?? 0;
  const count = q.data?.count ?? 0;

  const hasFiltros = !!(emisor || estado || desde || hasta);

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-5xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office · Facturación ARCA
        </div>
        <h1 className="font-display text-3xl text-ink">Facturas electrónicas</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Registro de facturas y notas de crédito emitidas ante ARCA (ex-AFIP).
        </p>
      </header>

      {/* Filtros */}
      <div className="flex flex-wrap items-end gap-3">
        <Segment
          label="Emisor"
          value={emisor}
          onChange={setEmisor}
          options={[["", "Todos"], ...EMISORES.map((e) => [e, e[0].toUpperCase() + e.slice(1)] as [string, string])]}
        />
        <Segment
          label="Estado"
          value={estado}
          onChange={setEstado}
          options={[["", "Todos"], ...ESTADOS_FACTURA.map((s) => [s, s[0].toUpperCase() + s.slice(1)] as [string, string])]}
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
        {hasFiltros && (
          <button
            type="button"
            onClick={() => {
              setEmisor("");
              setEstado("");
              setDesde("");
              setHasta("");
            }}
            className="h-9 text-xs text-muted-foreground hover:text-ink underline"
          >
            Limpiar
          </button>
        )}
      </div>

      {/* Total */}
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
          Total facturado {q.data ? `(${count})` : ""}
        </span>
        <span className="font-mono text-xl font-semibold tabular-nums text-ink">
          {formatARS(totalImp)}
        </span>
      </div>

      {q.isLoading && <div className="text-sm text-muted-foreground">Cargando facturas…</div>}
      {q.isError && (
        <div className="text-sm text-destructive">
          Error cargando las facturas. {(q.error as Error)?.message}
        </div>
      )}

      {/* Tabla */}
      {facturas.length > 0 && (
        <div className="overflow-x-auto rounded-xl border hairline">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b hairline bg-surface-elevated text-left">
                <th className="px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                  Fecha
                </th>
                <th className="px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                  Comprobante
                </th>
                <th className="px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                  Pedido
                </th>
                <th className="px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                  Receptor
                </th>
                <th className="px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground text-right">
                  Total
                </th>
                <th className="px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                  Estado
                </th>
              </tr>
            </thead>
            <tbody className="divide-y hairline">
              {facturas.map((f) => {
                const letra =
                  { 1: "A", 3: "A", 6: "B", 8: "B", 11: "C", 13: "C" }[f.cbte_tipo] ?? "?";
                const esNC = [3, 8, 13].includes(f.cbte_tipo);
                const nroFmt = f.cbte_nro
                  ? `${String(f.pto_vta).padStart(5, "0")}-${String(f.cbte_nro).padStart(8, "0")}`
                  : "—";
                return (
                  <tr key={f.id} className="hover:bg-surface-elevated/60 transition-colors">
                    <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                      {f.fecha_emision ? formatFechaDisplay(f.fecha_emision) : "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-xs">
                        {esNC ? "NC" : "Fact."} {letra} {nroFmt}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <Link
                        to="/admin/pedidos/$id"
                        params={{ id: String(f.pedido_id) }}
                        className="font-mono text-xs text-muted-foreground hover:text-ink"
                      >
                        #{f.pedido_id}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground max-w-[160px] truncate">
                      {f.razon_social ?? f.cliente_cuit ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-right tabular-nums">
                      {formatARS(f.imp_total)}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-1.5">
                        <FacturaBadge estado={f.estado} />
                        {f.ambiente === "homologacion" && (
                          <span className="font-mono text-[9px] text-amber-600 border border-amber-400/50 rounded px-1">
                            TEST
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!q.isLoading && facturas.length === 0 && (
        <div className="text-sm text-muted-foreground py-8 text-center">
          {hasFiltros ? "Sin facturas para los filtros seleccionados." : "Todavía no hay facturas emitidas."}
        </div>
      )}
    </div>
  );
}

// ── Helpers de UI ─────────────────────────────────────────────────────────────

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
      {children}
    </div>
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
      <div className="flex items-center rounded-md border hairline overflow-hidden h-9">
        {options.map(([v, l]) => (
          <button
            key={v}
            type="button"
            onClick={() => onChange(v)}
            className={cn(
              "px-2.5 h-full text-xs font-medium transition-colors",
              value === v
                ? "bg-ink text-background"
                : "bg-surface-elevated text-muted-foreground hover:text-ink",
            )}
          >
            {l}
          </button>
        ))}
      </div>
    </div>
  );
}
