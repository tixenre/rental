/**
 * contabilidad.movimientos.lazy.tsx — Libro de movimientos (#809, Fase 2/3).
 *
 * Registra y lista los movimientos manuales de plata: gastos, transferencias
 * entre cajas, retiros y aportes de socios. Los cobros de clientes NO van acá
 * (entran solos desde Pagos). La plata nunca se borra: anular deja el registro
 * tachado con su motivo.
 */
import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  adminApi,
  TIPOS_MOVIMIENTO,
  type Cuenta,
  type Movimiento,
  type MovimientoInput,
  type TipoMovimiento,
} from "@/lib/admin/api";
import { formatMoney, formatFechaDisplay } from "@/lib/format";
import { useDocumentTitle } from "@/lib/use-document-title";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export const Route = createLazyFileRoute("/admin/contabilidad/movimientos")({
  component: MovimientosPage,
});

const TIPO_LABEL: Record<TipoMovimiento, string> = {
  gasto: "Gasto",
  transferencia: "Transferencia",
  retiro: "Retiro",
  aporte: "Aporte",
  ajuste: "Ajuste",
};

function descMovimiento(m: Movimiento): string {
  const o = m.cuenta_origen_nombre ?? "—";
  const d = m.cuenta_destino_nombre ?? "—";
  switch (m.tipo) {
    case "gasto":
      return `${m.categoria_nombre ?? "Sin categoría"} · sale de ${o}`;
    case "transferencia":
      return `${o} → ${d}`;
    case "retiro":
      return `Retiro de ${o}`;
    case "aporte":
      return `Aporte a ${d}`;
    default:
      return [o !== "—" ? o : null, d !== "—" ? d : null].filter(Boolean).join(" → ") || "Ajuste";
  }
}

function MovimientosPage() {
  useDocumentTitle("Movimientos · Finanzas");
  const qc = useQueryClient();
  const [tipoFiltro, setTipoFiltro] = useState<string>("");

  const invalidar = () => qc.invalidateQueries({ queryKey: ["admin", "contabilidad"] });

  const movsQ = useQuery({
    queryKey: ["admin", "contabilidad", "movimientos", { tipo: tipoFiltro }],
    queryFn: () => adminApi.listMovimientos({ tipo: tipoFiltro || undefined }),
  });

  const movimientos = movsQ.data?.movimientos ?? [];

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-5xl mx-auto">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office · Finanzas
          </div>
          <h1 className="font-display text-3xl text-ink">Movimientos</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Gastos, transferencias entre cajas, retiros y aportes. Los cobros de clientes entran
            solos desde Pagos.
          </p>
        </div>
        <Link
          to="/admin/contabilidad"
          className="shrink-0 h-9 rounded-md border hairline px-3 text-sm flex items-center hover:bg-muted/40"
        >
          ← Tablero
        </Link>
      </header>

      <NuevoMovimientoForm onCreated={invalidar} />

      {/* Filtro por tipo */}
      <div className="flex flex-wrap gap-1">
        {[
          ["", "Todos"],
          ...TIPOS_MOVIMIENTO.map((t) => [t, TIPO_LABEL[t]] as [string, string]),
        ].map(([val, lbl]) => (
          <button
            key={val}
            type="button"
            onClick={() => setTipoFiltro(val)}
            className={cn(
              "rounded-md border px-2.5 py-1.5 text-xs font-medium transition",
              tipoFiltro === val
                ? "border-ink bg-ink text-background"
                : "border-muted-foreground/30 text-muted-foreground hover:border-ink hover:text-ink",
            )}
          >
            {lbl}
          </button>
        ))}
      </div>

      {movsQ.isLoading && (
        <div className="text-sm text-muted-foreground">Cargando movimientos…</div>
      )}
      {movsQ.isError && (
        <div className="text-sm text-destructive">
          Error cargando los movimientos. {(movsQ.error as Error)?.message}
        </div>
      )}

      {movsQ.data && movimientos.length === 0 && (
        <div className="text-sm text-muted-foreground border rounded-lg p-6 text-center">
          Todavía no hay movimientos para este filtro.
        </div>
      )}

      {movimientos.length > 0 && (
        <div className="overflow-x-auto rounded-lg border hairline">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b hairline text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-3 py-2 font-medium">Fecha</th>
                <th className="px-3 py-2 font-medium">Tipo</th>
                <th className="px-3 py-2 font-medium">Detalle</th>
                <th className="px-3 py-2 font-medium text-right">Monto</th>
                <th className="px-3 py-2 font-medium text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {movimientos.map((m) => (
                <MovimientoRow key={m.id} mov={m} onChanged={invalidar} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MovimientoRow({ mov, onChanged }: { mov: Movimiento; onChanged: () => void }) {
  const anular = useMutation({
    mutationFn: (motivo: string) => adminApi.anularMovimiento(mov.id, motivo),
    onSuccess: () => {
      toast.success("Movimiento anulado");
      onChanged();
    },
    onError: (e) => toast.error("No se pudo anular", { description: (e as Error).message }),
  });

  return (
    <tr className={cn("border-b hairline last:border-0", mov.anulado && "opacity-50")}>
      <td className="px-3 py-2 whitespace-nowrap text-muted-foreground">
        {formatFechaDisplay(mov.fecha)}
      </td>
      <td className="px-3 py-2">
        <Badge variant="secondary">{TIPO_LABEL[mov.tipo]}</Badge>
      </td>
      <td className="px-3 py-2">
        <span className={cn(mov.anulado && "line-through")}>{descMovimiento(mov)}</span>
        {mov.nota && <div className="text-[11px] text-muted-foreground">{mov.nota}</div>}
        {mov.anulado && mov.anulado_motivo && (
          <div className="text-[11px] text-destructive">Anulado: {mov.anulado_motivo}</div>
        )}
        {mov.comprobante_url && (
          <a
            href={mov.comprobante_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-amber hover:underline"
          >
            Ver comprobante
          </a>
        )}
      </td>
      <td className="px-3 py-2 text-right font-mono tabular-nums">
        {formatMoney(mov.monto, mov.moneda)}
      </td>
      <td className="px-3 py-2 text-right">
        {!mov.anulado && (
          <button
            type="button"
            onClick={() => {
              const motivo = window.prompt("Motivo de la anulación:");
              if (motivo && motivo.trim()) anular.mutate(motivo.trim());
            }}
            disabled={anular.isPending}
            className="text-xs text-muted-foreground hover:text-destructive underline"
          >
            Anular
          </button>
        )}
      </td>
    </tr>
  );
}

function NuevoMovimientoForm({ onCreated }: { onCreated: () => void }) {
  const [tipo, setTipo] = useState<TipoMovimiento>("gasto");
  const [monto, setMonto] = useState("");
  const [origen, setOrigen] = useState("");
  const [destino, setDestino] = useState("");
  const [categoria, setCategoria] = useState("");
  const [metodo, setMetodo] = useState("");
  const [fecha, setFecha] = useState("");
  const [nota, setNota] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const cuentasQ = useQuery({
    queryKey: ["admin", "contabilidad", "cuentas-list"],
    queryFn: () => adminApi.listCuentas(),
  });
  const catsQ = useQuery({
    queryKey: ["admin", "contabilidad", "categorias"],
    queryFn: () => adminApi.listGastoCategorias(),
  });

  const cuentas: Cuenta[] = cuentasQ.data?.cuentas ?? [];
  const categorias = catsQ.data?.categorias ?? [];

  const muestra = useMemo(
    () => ({
      origen:
        tipo === "gasto" || tipo === "transferencia" || tipo === "retiro" || tipo === "ajuste",
      destino: tipo === "transferencia" || tipo === "aporte" || tipo === "ajuste",
      categoria: tipo === "gasto",
    }),
    [tipo],
  );

  const reset = () => {
    setMonto("");
    setOrigen("");
    setDestino("");
    setCategoria("");
    setMetodo("");
    setFecha("");
    setNota("");
    setFile(null);
  };

  const crear = useMutation({
    mutationFn: async () => {
      const body: MovimientoInput = {
        tipo,
        monto: Number(monto) || 0,
        cuenta_origen_id: muestra.origen && origen ? Number(origen) : null,
        cuenta_destino_id: muestra.destino && destino ? Number(destino) : null,
        categoria_id: muestra.categoria && categoria ? Number(categoria) : null,
        metodo: metodo || null,
        fecha: fecha || null,
        nota: nota || null,
      };
      const mov = await adminApi.createMovimiento(body);
      if (file) await adminApi.uploadComprobante(mov.id, file);
      return mov;
    },
    onSuccess: () => {
      reset();
      toast.success("Movimiento registrado");
      onCreated();
    },
    onError: (e) => toast.error("No se pudo registrar", { description: (e as Error).message }),
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!(Number(monto) > 0)) {
          toast.error("Poné un monto mayor a cero");
          return;
        }
        crear.mutate();
      }}
      className="rounded-lg border hairline p-4 space-y-3"
    >
      <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
        Nuevo movimiento
      </div>

      {/* Tipo */}
      <div className="flex flex-wrap gap-1">
        {TIPOS_MOVIMIENTO.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTipo(t)}
            className={cn(
              "rounded-md border px-2.5 py-1.5 text-xs font-medium transition",
              tipo === t
                ? "border-ink bg-ink text-background"
                : "border-muted-foreground/30 text-muted-foreground hover:border-ink hover:text-ink",
            )}
          >
            {TIPO_LABEL[t]}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Field label="Monto">
          <input
            type="number"
            value={monto}
            onChange={(e) => setMonto(e.target.value)}
            className="h-9 w-32 rounded-md border hairline bg-surface-elevated px-2 text-right text-sm tabular-nums"
          />
        </Field>

        {muestra.origen && (
          <Field label={tipo === "retiro" ? "Saca de" : "Sale de"}>
            <CuentaSelect cuentas={cuentas} value={origen} onChange={setOrigen} />
          </Field>
        )}
        {muestra.destino && (
          <Field label="Entra a">
            <CuentaSelect cuentas={cuentas} value={destino} onChange={setDestino} />
          </Field>
        )}
        {muestra.categoria && (
          <Field label="Categoría">
            <select
              value={categoria}
              onChange={(e) => setCategoria(e.target.value)}
              className="h-9 rounded-md border hairline bg-surface-elevated px-2 text-sm"
            >
              <option value="">Elegir…</option>
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field label="Método">
          <select
            value={metodo}
            onChange={(e) => setMetodo(e.target.value)}
            className="h-9 rounded-md border hairline bg-surface-elevated px-2 text-sm capitalize"
          >
            <option value="">—</option>
            <option value="transferencia">transferencia</option>
            <option value="efectivo">efectivo</option>
          </select>
        </Field>
        <Field label="Fecha">
          <input
            type="date"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
            className="h-9 rounded-md border hairline bg-surface-elevated px-2 text-sm"
          />
        </Field>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Field label="Nota (opcional)">
          <input
            value={nota}
            onChange={(e) => setNota(e.target.value)}
            placeholder="Ej. factura 0001-…"
            className="h-9 w-64 rounded-md border hairline bg-surface-elevated px-2 text-sm"
          />
        </Field>
        <Field label="Comprobante (opcional)">
          <input
            type="file"
            accept="application/pdf,image/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-xs"
          />
        </Field>
        <button
          type="submit"
          disabled={crear.isPending}
          className="h-9 rounded-md bg-ink px-4 text-sm text-background disabled:opacity-50"
        >
          {crear.isPending ? "Guardando…" : "Registrar"}
        </button>
      </div>
    </form>
  );
}

function CuentaSelect({
  cuentas,
  value,
  onChange,
}: {
  cuentas: Cuenta[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 rounded-md border hairline bg-surface-elevated px-2 text-sm"
    >
      <option value="">Elegir…</option>
      {cuentas.map((c) => (
        <option key={c.id} value={c.id}>
          {c.nombre}
        </option>
      ))}
    </select>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="space-y-1">
      <span className="block font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}
