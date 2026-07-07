/**
 * facturacion.exportacion.lazy.tsx — Factura de Exportación (WSFEXv1).
 *
 * Flujo NUEVO sin pedido de por medio (venta al exterior, carga manual): listado + alta +
 * nota de crédito. Espeja el pattern de facturas.lazy.tsx (listado global de facturas ARCA).
 */
import { createLazyFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, RefreshCw, Undo2, Eye, Download } from "lucide-react";

import {
  facturacionApi,
  type FacturaExportacion,
  type NuevaFacturaExportacion,
} from "@/lib/admin/api";
import { formatARS, formatFechaDisplay } from "@/lib/format";
import { useDocumentTitle } from "@/lib/use-document-title";
import { FacturaBadge } from "@/components/kit/FacturaBadge";
import { cn } from "@/lib/utils";

export const Route = createLazyFileRoute("/admin/facturacion/exportacion")({
  component: FacturaExportacionPage,
});

const ESTADOS = ["pendiente", "emitida", "error", "anulada"] as const;
const CONCEPTOS = [
  { value: 1, label: "Productos" },
  { value: 2, label: "Servicios" },
  { value: 3, label: "Productos y Servicios" },
];

function FacturaExportacionPage() {
  useDocumentTitle("Factura de Exportación · Back Office");
  const qc = useQueryClient();

  const [emisor, setEmisor] = useState("");
  const [estado, setEstado] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [ncDe, setNcDe] = useState<FacturaExportacion | null>(null);

  const q = useQuery({
    queryKey: ["admin", "facturas-exportacion", { emisor, estado }],
    queryFn: () =>
      facturacionApi.listFacturasExportacion({
        emisor: emisor || undefined,
        estado: estado || undefined,
      }),
  });

  const emisores = useQuery({
    queryKey: ["admin", "emisores-arca"],
    queryFn: () => facturacionApi.listEmisores(),
  });

  const catalogos = useQuery({
    queryKey: ["admin", "catalogos-exportacion"],
    queryFn: () => facturacionApi.getCatalogosExportacion(),
    retry: false,
  });

  const refrescarCatalogos = useMutation({
    mutationFn: () => facturacionApi.refrescarCatalogosExportacion(),
    onSuccess: () => {
      toast.success("Catálogos de exportación actualizados");
      qc.invalidateQueries({ queryKey: ["admin", "catalogos-exportacion"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const facturas = q.data?.facturas ?? [];
  const emisoresHabilitados = (emisores.data ?? []).filter(
    (e) => e.activo && e.cert_cargado && e.habilitado_exportacion,
  );
  const hasFiltros = !!(emisor || estado);

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-5xl mx-auto">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="font-mono text-2xs uppercase tracking-[0.25em] text-muted-foreground">
            Back-office · Facturación ARCA
          </div>
          <h1 className="font-display text-3xl text-ink">Factura de Exportación</h1>
          <p className="text-sm text-muted-foreground mt-1">
            WSFEXv1 — venta al exterior, sin pedido de alquiler de por medio. Carga manual.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => refrescarCatalogos.mutate()}
            disabled={refrescarCatalogos.isPending}
            className="h-9 px-3 rounded-md border hairline text-sm text-muted-foreground hover:text-ink flex items-center gap-1.5 disabled:opacity-50"
          >
            <RefreshCw
              className={cn("h-3.5 w-3.5", refrescarCatalogos.isPending && "animate-spin")}
            />
            Actualizar catálogos
          </button>
          <button
            type="button"
            onClick={() => setShowForm(true)}
            disabled={emisoresHabilitados.length === 0}
            title={
              emisoresHabilitados.length === 0
                ? "Ningún emisor está habilitado para exportación (marcalo en Emisores ARCA)"
                : undefined
            }
            className="h-9 px-4 rounded-md bg-ink text-background text-sm font-medium flex items-center gap-1.5 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            Nueva factura
          </button>
        </div>
      </header>

      {catalogos.isError && (
        <div className="rounded-lg border hairline bg-surface-elevated p-3 text-sm text-muted-foreground">
          Los catálogos de país destino/Incoterm/moneda todavía no se actualizaron — "Actualizar
          catálogos" antes de cargar una factura.
        </div>
      )}

      {/* Filtros */}
      <div className="flex flex-wrap items-end gap-3">
        <Segment
          label="Emisor"
          value={emisor}
          onChange={setEmisor}
          options={[
            ["", "Todos"],
            ...(emisores.data ?? []).map((e) => [e.nombre, e.nombre] as [string, string]),
          ]}
        />
        <Segment
          label="Estado"
          value={estado}
          onChange={setEstado}
          options={[["", "Todos"], ...ESTADOS.map((s) => [s, s] as [string, string])]}
        />
        {hasFiltros && (
          <button
            type="button"
            onClick={() => {
              setEmisor("");
              setEstado("");
            }}
            className="h-9 text-xs text-muted-foreground hover:text-ink underline"
          >
            Limpiar
          </button>
        )}
      </div>

      {q.isLoading && <div className="text-sm text-muted-foreground">Cargando facturas…</div>}
      {q.isError && (
        <div className="text-sm text-destructive">
          Error cargando las facturas. {(q.error as Error)?.message}
        </div>
      )}

      {facturas.length > 0 && (
        <div className="overflow-x-auto rounded-xl border hairline">
          {/* eslint-disable-next-line no-restricted-syntax -- tabla de solo lectura con rendering complejo por celda */}
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b hairline bg-surface-elevated text-left">
                <Th>Fecha</Th>
                <Th>Comprobante</Th>
                <Th>Receptor</Th>
                <Th>País destino</Th>
                <Th className="text-right">Total</Th>
                <Th>Estado</Th>
                <Th />
              </tr>
            </thead>
            <tbody className="divide-y hairline">
              {facturas.map((f) => {
                const nroFmt = f.cbte_nro
                  ? `${String(f.pto_vta).padStart(5, "0")}-${String(f.cbte_nro).padStart(8, "0")}`
                  : "—";
                const esNC = f.nota_credito_de !== null || f.cbte_tipo === 21;
                return (
                  <tr key={f.id} className="hover:bg-surface-elevated/60 transition-colors">
                    <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                      {f.fecha_emision ? formatFechaDisplay(f.fecha_emision) : "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-xs">
                        {esNC ? "NC E" : "Fact. E"} {nroFmt}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground max-w-[180px] truncate">
                      {f.receptor_razon_social}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">
                      {f.receptor_pais_destino}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-right tabular-nums">
                      {f.moneda === "PES" ? formatARS(f.imp_total) : `${f.moneda} ${f.imp_total}`}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-1.5">
                        <FacturaBadge estado={f.estado} />
                        {f.ambiente === "homologacion" && (
                          // eslint-disable-next-line no-restricted-syntax -- text-[9px]: menor que text-2xs, sin equiv DS; amber: paleta categórica homologación (Tier 3)
                          <span className="font-mono text-[9px] text-amber-600 border border-amber-400/50 rounded px-1">
                            TEST
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      {f.estado === "emitida" && (
                        <div className="flex items-center gap-2.5 justify-end">
                          <a
                            href={`/api/facturas-exportacion/${f.id}/pdf?format=html`}
                            target="_blank"
                            rel="noreferrer"
                            title="Ver"
                            className="text-muted-foreground hover:text-ink"
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </a>
                          <a
                            href={`/api/facturas-exportacion/${f.id}/pdf`}
                            target="_blank"
                            rel="noreferrer"
                            title="Descargar PDF"
                            className="text-muted-foreground hover:text-ink"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </a>
                          {!esNC && (
                            <button
                              type="button"
                              onClick={() => setNcDe(f)}
                              title="Emitir Nota de Crédito"
                              className="text-muted-foreground hover:text-ink"
                            >
                              <Undo2 className="h-3.5 w-3.5" />
                            </button>
                          )}
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
            : "Todavía no hay Facturas de Exportación emitidas."}
        </div>
      )}

      {showForm && (
        <FacturaExportacionFormModal
          onClose={() => setShowForm(false)}
          onSaved={() => {
            setShowForm(false);
            qc.invalidateQueries({ queryKey: ["admin", "facturas-exportacion"] });
          }}
          emisores={emisoresHabilitados}
          catalogos={catalogos.data}
        />
      )}

      {ncDe && (
        <NotaCreditoModal
          factura={ncDe}
          emisores={emisores.data ?? []}
          onClose={() => setNcDe(null)}
          onSaved={() => {
            setNcDe(null);
            qc.invalidateQueries({ queryKey: ["admin", "facturas-exportacion"] });
          }}
        />
      )}
    </div>
  );
}

// ── Alta ─────────────────────────────────────────────────────────────────────

function FacturaExportacionFormModal({
  onClose,
  onSaved,
  emisores,
  catalogos,
}: {
  onClose: () => void;
  onSaved: () => void;
  emisores: Awaited<ReturnType<typeof facturacionApi.listEmisores>>;
  catalogos?: Awaited<ReturnType<typeof facturacionApi.getCatalogosExportacion>>;
}) {
  const [nombreEmisor, setNombreEmisor] = useState(emisores[0]?.nombre ?? "");
  const [razonSocial, setRazonSocial] = useState("");
  const [paisDestino, setPaisDestino] = useState(String(catalogos?.paises_destino[0]?.id ?? ""));
  const [domicilio, setDomicilio] = useState("");
  const [idImpositivo, setIdImpositivo] = useState("");
  const [incoterm, setIncoterm] = useState(String(catalogos?.incoterms[0]?.id ?? ""));
  const [permisoEmbarque, setPermisoEmbarque] = useState("");
  const [concepto, setConcepto] = useState(1);
  const [importeNeto, setImporteNeto] = useState("");
  const [fecha, setFecha] = useState(() => new Date().toISOString().slice(0, 10));
  const [moneda, setMoneda] = useState(String(catalogos?.monedas[0]?.id ?? ""));
  const [cotizacion, setCotizacion] = useState("1");

  const emisorSel = emisores.find((e) => e.nombre === nombreEmisor);

  const crear = useMutation({
    mutationFn: () => {
      if (!emisorSel) throw new Error("Elegí un emisor");
      const body: NuevaFacturaExportacion = {
        nombre_emisor: nombreEmisor,
        emisor: {
          cuit: emisorSel.cuit,
          punto_venta: emisorSel.pto_vta,
          condicion_iva: emisorSel.condicion_iva,
        },
        receptor: {
          razon_social: razonSocial,
          pais_destino_id: Number(paisDestino),
          domicilio: domicilio || undefined,
          id_impositivo: idImpositivo || undefined,
        },
        exportacion: {
          incoterm,
          permiso_embarque: permisoEmbarque || undefined,
          permiso_existente: permisoEmbarque.length > 0,
        },
        concepto,
        importe_neto: importeNeto,
        fecha,
        moneda,
        cotizacion,
      };
      return facturacionApi.crearFacturaExportacion(body);
    },
    onSuccess: () => {
      toast.success("Factura de Exportación emitida");
      onSaved();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Overlay onClose={onClose}>
      <h2 className="font-display text-xl text-ink mb-4">Nueva Factura de Exportación</h2>
      <div className="space-y-4">
        <Field label="Emisor">
          {}
          <select
            value={nombreEmisor}
            onChange={(e) => setNombreEmisor(e.target.value)}
            className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm"
          >
            {emisores.map((e) => (
              <option key={e.nombre} value={e.nombre}>
                {e.nombre}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Razón social del receptor">
          {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad */}
          <input
            type="text"
            value={razonSocial}
            onChange={(e) => setRazonSocial(e.target.value)}
            className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="País destino">
            {}
            <select
              value={paisDestino}
              onChange={(e) => setPaisDestino(e.target.value)}
              className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm"
            >
              {(catalogos?.paises_destino ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.desc}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Incoterm">
            {}
            <select
              value={incoterm}
              onChange={(e) => setIncoterm(e.target.value)}
              className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm"
            >
              {(catalogos?.incoterms ?? []).map((i) => (
                <option key={i.id} value={i.id}>
                  {i.desc}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field label="Domicilio del receptor (opcional)">
          {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad */}
          <input
            type="text"
            value={domicilio}
            onChange={(e) => setDomicilio(e.target.value)}
            className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm"
          />
        </Field>
        <Field label="Id. impositivo del receptor (opcional)">
          {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad */}
          <input
            type="text"
            value={idImpositivo}
            onChange={(e) => setIdImpositivo(e.target.value)}
            className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm"
          />
        </Field>
        <Field
          label="Permiso de embarque"
          hint="Vacío = sin permiso existente al momento de facturar"
        >
          {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad */}
          <input
            type="text"
            value={permisoEmbarque}
            onChange={(e) => setPermisoEmbarque(e.target.value)}
            className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm font-mono"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Concepto">
            {}
            <select
              value={concepto}
              onChange={(e) => setConcepto(Number(e.target.value))}
              className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm"
            >
              {CONCEPTOS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Fecha">
            {/* eslint-disable-next-line no-restricted-syntax -- type="date" nativo, Input DS no soporta este tipo */}
            <input
              type="date"
              value={fecha}
              onChange={(e) => setFecha(e.target.value)}
              className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm"
            />
          </Field>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Importe neto">
            {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad */}
            <input
              type="text"
              inputMode="decimal"
              value={importeNeto}
              onChange={(e) => setImporteNeto(e.target.value)}
              placeholder="1000.00"
              className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm font-mono"
            />
          </Field>
          <Field label="Moneda">
            {}
            <select
              value={moneda}
              onChange={(e) => setMoneda(e.target.value)}
              className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm"
            >
              {(catalogos?.monedas ?? []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.id}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Cotización">
            {/* eslint-disable-next-line no-restricted-syntax -- input nativo en modal de baja complejidad */}
            <input
              type="text"
              inputMode="decimal"
              value={cotizacion}
              onChange={(e) => setCotizacion(e.target.value)}
              className="w-full h-9 rounded-md border hairline bg-surface-elevated px-3 text-sm font-mono"
            />
          </Field>
        </div>
      </div>
      <div className="flex justify-end gap-2 mt-5">
        <button
          type="button"
          onClick={onClose}
          className="h-9 px-4 rounded-md border hairline text-sm text-muted-foreground hover:text-ink"
        >
          Cancelar
        </button>
        <button
          type="button"
          onClick={() => crear.mutate()}
          disabled={crear.isPending || !razonSocial || !paisDestino || !incoterm || !importeNeto}
          className="h-9 px-4 rounded-md bg-ink text-background text-sm font-medium disabled:opacity-50"
        >
          {crear.isPending ? "Emitiendo…" : "Emitir factura"}
        </button>
      </div>
    </Overlay>
  );
}

// ── Nota de crédito ────────────────────────────────────────────────────────────

function NotaCreditoModal({
  factura,
  emisores,
  onClose,
  onSaved,
}: {
  factura: FacturaExportacion;
  emisores: Awaited<ReturnType<typeof facturacionApi.listEmisores>>;
  onClose: () => void;
  onSaved: () => void;
}) {
  const emisorSel = emisores.find((e) => e.nombre === factura.emisor);

  const nc = useMutation({
    mutationFn: () => {
      if (!emisorSel) throw new Error(`No se encontró el emisor '${factura.emisor}'`);
      return facturacionApi.notaCreditoExportacion(factura.id, {
        nombre_emisor: factura.emisor,
        emisor: {
          cuit: emisorSel.cuit,
          punto_venta: factura.pto_vta,
          condicion_iva: emisorSel.condicion_iva,
        },
        receptor: {
          razon_social: factura.receptor_razon_social,
          pais_destino_id: factura.receptor_pais_destino,
          domicilio: factura.receptor_domicilio ?? undefined,
          id_impositivo: factura.receptor_id_impositivo ?? undefined,
        },
        exportacion: {
          incoterm: factura.incoterm,
          permiso_embarque: factura.permiso_embarque ?? undefined,
        },
        importe_neto: String(factura.imp_total),
        fecha: new Date().toISOString().slice(0, 10),
        moneda: factura.moneda,
        cotizacion: String(factura.cotizacion),
        cbtes_asoc: [
          { tipo: factura.cbte_tipo, punto_venta: factura.pto_vta, numero: factura.cbte_nro },
        ],
      });
    },
    onSuccess: () => {
      toast.success("Nota de Crédito emitida");
      onSaved();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Overlay onClose={onClose}>
      <h2 className="font-display text-xl text-ink mb-2">Nota de Crédito de Exportación</h2>
      <p className="text-sm text-muted-foreground mb-5">
        Anula la Factura E {String(factura.pto_vta).padStart(5, "0")}-
        {String(factura.cbte_nro).padStart(8, "0")} de {factura.receptor_razon_social} por{" "}
        {factura.moneda} {factura.imp_total}.
      </p>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onClose}
          className="h-9 px-4 rounded-md border hairline text-sm text-muted-foreground hover:text-ink"
        >
          Cancelar
        </button>
        <button
          type="button"
          onClick={() => nc.mutate()}
          disabled={nc.isPending}
          className="h-9 px-4 rounded-md bg-ink text-background text-sm font-medium disabled:opacity-50"
        >
          {nc.isPending ? "Emitiendo…" : "Emitir Nota de Crédito"}
        </button>
      </div>
    </Overlay>
  );
}

// ── Helpers UI ─────────────────────────────────────────────────────────────────

function Th({ children, className }: { children?: React.ReactNode; className?: string }) {
  return (
    <th
      className={cn(
        "px-4 py-2.5 font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground",
        className,
      )}
    >
      {children}
    </th>
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
      <div className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
        {label}
      </div>
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

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <div className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
        {label}
      </div>
      {hint && <p className="text-xs text-muted-foreground/70 -mt-0.5">{hint}</p>}
      {children}
    </div>
  );
}

function Overlay({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg max-h-[85vh] overflow-y-auto rounded-2xl bg-background border hairline shadow-xl p-6">
        {children}
      </div>
    </div>
  );
}
