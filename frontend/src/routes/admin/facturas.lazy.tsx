/**
 * facturas.lazy.tsx — Listado global de facturas electrónicas ARCA.
 *
 * Vista de solo-lectura sobre la tabla `facturas`, con filtros por emisor,
 * estado y rango de fechas. Espeja el pattern de pagos.lazy.tsx.
 */
import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, Eye, Mail } from "lucide-react";
import { toast } from "sonner";

import { facturacionApi, type FacturaEstado } from "@/lib/admin/api";
import { formatARS, formatFechaDisplay } from "@/lib/format";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { FacturaBadge } from "@/design-system/ui/FacturaBadge";
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

  const enviarMail = useMutation({
    mutationFn: (facturaId: number) => facturacionApi.enviarMailFactura(facturaId),
    onSuccess: (data) => toast.success(`Factura enviada a ${data.to}`),
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-5xl mx-auto">
      <header>
        <div className="font-mono text-2xs uppercase tracking-[0.25em] text-muted-foreground">
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
          options={[
            ["", "Todos"],
            ...EMISORES.map((e) => [e, e[0].toUpperCase() + e.slice(1)] as [string, string]),
          ]}
        />
        <Segment
          label="Estado"
          value={estado}
          onChange={setEstado}
          options={[
            ["", "Todos"],
            ...ESTADOS_FACTURA.map((s) => [s, s[0].toUpperCase() + s.slice(1)] as [string, string]),
          ]}
        />
        <div className="space-y-1">
          <FieldLabel>Desde</FieldLabel>
          {/* eslint-disable-next-line no-restricted-syntax -- type="date" nativo, Input DS no soporta este tipo */}
          <input
            type="date"
            value={desde}
            onChange={(e) => setDesde(e.target.value)}
            className="h-9 rounded-md border hairline bg-surface-elevated px-2 text-sm"
          />
        </div>
        <div className="space-y-1">
          <FieldLabel>Hasta</FieldLabel>
          {/* eslint-disable-next-line no-restricted-syntax -- type="date" nativo, Input DS no soporta este tipo */}
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
        <span className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
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
          {/* eslint-disable-next-line no-restricted-syntax -- tabla de solo lectura con rendering complejo por celda */}
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b hairline bg-surface-elevated text-left">
                <th className="px-4 py-2.5 font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
                  Fecha
                </th>
                <th className="px-4 py-2.5 font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
                  Comprobante
                </th>
                <th className="px-4 py-2.5 font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
                  Pedido
                </th>
                <th className="px-4 py-2.5 font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
                  Receptor
                </th>
                <th className="px-4 py-2.5 font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground text-right">
                  Total
                </th>
                <th className="px-4 py-2.5 font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
                  Estado
                </th>
                <th className="px-4 py-2.5 font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground" />
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
                const enviandoEsta = enviarMail.isPending && enviarMail.variables === f.id;
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
                          // eslint-disable-next-line no-restricted-syntax -- amber: paleta categórica homologación (Tier 3)
                          <span className="font-mono text-3xs text-amber-600 border border-amber-400/50 rounded px-1">
                            TEST
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      {f.estado === "emitida" && (
                        <div className="flex items-center gap-2.5 justify-end">
                          <a
                            href={`/api/facturas/${f.id}/pdf?format=html`}
                            target="_blank"
                            rel="noreferrer"
                            title="Ver"
                            className="text-muted-foreground hover:text-ink"
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </a>
                          <a
                            href={`/api/facturas/${f.id}/pdf`}
                            target="_blank"
                            rel="noreferrer"
                            title="Descargar PDF"
                            className="text-muted-foreground hover:text-ink"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </a>
                          <button
                            type="button"
                            onClick={() => enviarMail.mutate(f.id)}
                            disabled={enviandoEsta}
                            title="Enviar por mail"
                            className="text-muted-foreground hover:text-ink disabled:opacity-50"
                          >
                            <Mail className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!q.isLoading && facturas.length === 0 && (
        <div className="py-8 text-center text-sm text-muted-foreground">
          {hasFiltros
            ? "Sin facturas para los filtros seleccionados."
            : "Todavía no hay facturas emitidas."}
        </div>
      )}
    </div>
  );
}

// ── Helpers de UI ─────────────────────────────────────────────────────────────

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
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
