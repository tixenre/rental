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
  type CobroMensual,
  type Cuenta,
  type Movimiento,
  type MovimientoInput,
  type TipoMovimiento,
} from "@/lib/admin/api";
import { AdminPage } from "@/components/admin/AdminPage";
import { formatMoney, formatFechaDisplay } from "@/lib/format";
import { useDocumentTitle } from "@/lib/use-document-title";
import { Badge } from "@/design-system/ui/badge";
import { TipoMovimientoBadge, TIPO_MOVIMIENTO_META } from "@/components/admin/badges";
import { cn } from "@/lib/utils";

export const Route = createLazyFileRoute("/admin/contabilidad/movimientos")({
  component: MovimientosPage,
});

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

type Fila =
  | { kind: "mov"; fecha: string; mov: Movimiento }
  | { kind: "cobro"; fecha: string; cobro: CobroMensual };

// Fecha del último día del mes (para ordenar la línea de cobro al cierre del mes).
function finDeMes(mes: string): string {
  const [y, m] = mes.split("-").map(Number);
  const dia = new Date(y, m, 0).getDate();
  return `${mes}-${String(dia).padStart(2, "0")}`;
}

function mesLabel(mes: string): string {
  return new Date(`${mes}-01T00:00:00`).toLocaleDateString("es-AR", {
    month: "long",
    year: "numeric",
  });
}

// Dirección de la plata (guía visual estilo debe/haber): entra (haber, verde +),
// sale (debe, rojo −) o interno (transferencia/ajuste entre dos cajas, neutro).
type Direccion = "in" | "out" | "neutral";
function direccionMov(m: Movimiento): Direccion {
  const origen = !!m.cuenta_origen_id;
  const destino = !!m.cuenta_destino_id;
  if (origen && !destino) return "out";
  if (destino && !origen) return "in";
  return "neutral";
}
function montoClass(dir: Direccion): string {
  return dir === "in" ? "text-verde-ink" : dir === "out" ? "text-destructive" : "text-ink";
}
function montoSigno(dir: Direccion): string {
  return dir === "in" ? "+ " : dir === "out" ? "− " : "";
}

function MovimientosPage() {
  useDocumentTitle("Movimientos · Finanzas");
  const qc = useQueryClient();
  const [tipoFiltro, setTipoFiltro] = useState<string>("");
  const [beneficiarioFiltro, setBeneficiarioFiltro] = useState<string>("");

  const invalidar = () => qc.invalidateQueries({ queryKey: ["admin", "contabilidad"] });

  const movsQ = useQuery({
    queryKey: [
      "admin",
      "contabilidad",
      "movimientos",
      { tipo: tipoFiltro, ben: beneficiarioFiltro },
    ],
    queryFn: () =>
      adminApi.listMovimientos({
        tipo: tipoFiltro || undefined,
        beneficiario: beneficiarioFiltro || undefined,
      }),
  });

  // Vista unificada: movimientos manuales + cobros de pedidos (agregados por mes,
  // read-only), ordenados por fecha.
  const filas: Fila[] = [];
  if (movsQ.data) {
    for (const m of movsQ.data.movimientos) filas.push({ kind: "mov", fecha: m.fecha, mov: m });
    for (const c of movsQ.data.cobros ?? [])
      filas.push({ kind: "cobro", fecha: finDeMes(c.mes), cobro: c });
    filas.sort((a, b) => b.fecha.localeCompare(a.fecha));
  }

  return (
    <AdminPage
      title="Movimientos"
      maxW="max-w-5xl"
      description="Toda la plata de las cajas: los cobros de pedidos (que entran solos, una línea por mes) más los gastos, transferencias, retiros y aportes."
      backTo={{ to: "/admin/contabilidad", label: "Tablero" }}
    >
      <div className="space-y-6">
        <NuevoMovimientoForm onCreated={invalidar} />

        {/* Filtro por tipo */}
        <div className="flex flex-wrap gap-1">
          {[
            ["", "Todos"],
            ["cobro", "Cobros"],
            ...TIPOS_MOVIMIENTO.map((t) => [t, TIPO_MOVIMIENTO_META[t].label] as [string, string]),
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

        {beneficiarioFiltro && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Beneficiario:</span>
            <span className="rounded-md bg-ink px-2 py-0.5 text-xs text-background">
              {beneficiarioFiltro}
            </span>
            <button
              type="button"
              onClick={() => setBeneficiarioFiltro("")}
              className="text-xs text-muted-foreground hover:text-ink underline"
            >
              quitar
            </button>
          </div>
        )}

        {movsQ.data && filas.length === 0 && (
          <div className="text-sm text-muted-foreground border rounded-lg p-6 text-center">
            Todavía no hay movimientos para este filtro.
          </div>
        )}

        {filas.length > 0 && (
          <div className="overflow-x-auto rounded-lg border hairline">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b hairline text-left text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Fecha</th>
                  <th className="px-3 py-2 font-medium">Tipo</th>
                  <th className="px-3 py-2 font-medium">Detalle</th>
                  <th className="px-3 py-2 font-medium text-right">Monto</th>
                  <th className="px-3 py-2 font-medium text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f) =>
                  f.kind === "mov" ? (
                    <MovimientoRow
                      key={`m${f.mov.id}`}
                      mov={f.mov}
                      onChanged={invalidar}
                      onBeneficiario={setBeneficiarioFiltro}
                    />
                  ) : (
                    <CobroRow key={`c${f.cobro.mes}`} cobro={f.cobro} />
                  ),
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AdminPage>
  );
}

function MovimientoRow({
  mov,
  onChanged,
  onBeneficiario,
}: {
  mov: Movimiento;
  onChanged: () => void;
  onBeneficiario: (b: string) => void;
}) {
  const anular = useMutation({
    mutationFn: (motivo: string) => adminApi.anularMovimiento(mov.id, motivo),
    onSuccess: () => {
      toast.success("Movimiento anulado");
      onChanged();
    },
    onError: (e) => toast.error("No se pudo anular", { description: (e as Error).message }),
  });

  const dir = direccionMov(mov);

  return (
    <tr className={cn("border-b hairline last:border-0", mov.anulado && "opacity-50")}>
      <td className="px-3 py-2 whitespace-nowrap text-muted-foreground">
        {formatFechaDisplay(mov.fecha)}
      </td>
      <td className="px-3 py-2">
        <TipoMovimientoBadge tipo={mov.tipo} />
      </td>
      <td className="px-3 py-2">
        <span className={cn(mov.anulado && "line-through")}>{descMovimiento(mov)}</span>
        {mov.beneficiario && (
          <div>
            <button
              type="button"
              onClick={() => onBeneficiario(mov.beneficiario!)}
              className="text-xs text-ink underline decoration-amber/60 underline-offset-2 hover:decoration-amber"
              title="Ver el historial de este beneficiario"
            >
              {mov.beneficiario}
            </button>
          </div>
        )}
        {mov.nota && <div className="text-xs text-muted-foreground">{mov.nota}</div>}
        {mov.anulado && mov.anulado_motivo && (
          <div className="text-xs text-destructive">Anulado: {mov.anulado_motivo}</div>
        )}
        {mov.comprobante_url && (
          <a
            href={mov.comprobante_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-ink underline decoration-amber/60 underline-offset-2 hover:decoration-amber"
          >
            Ver comprobante
          </a>
        )}
      </td>
      <td className={cn("px-3 py-2 text-right font-mono tabular-nums", montoClass(dir))}>
        {montoSigno(dir)}
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

function CobroRow({ cobro }: { cobro: CobroMensual }) {
  return (
    <tr className="border-b hairline last:border-0 bg-muted/10">
      <td className="px-3 py-2 whitespace-nowrap capitalize text-muted-foreground">
        {mesLabel(cobro.mes)}
      </td>
      <td className="px-3 py-2">
        <Badge variant="secondary">Cobros</Badge>
      </td>
      <td className="px-3 py-2">
        <span className="capitalize text-ink">Cobro alquileres · {mesLabel(cobro.mes)}</span>
        <div className="text-xs text-muted-foreground">
          {cobro.cantidad} pago(s) ·{" "}
          <Link
            to="/admin/pagos"
            className="text-ink underline decoration-amber/60 underline-offset-2 hover:decoration-amber"
          >
            ver detalle
          </Link>
        </div>
      </td>
      <td className="px-3 py-2 text-right font-mono tabular-nums text-verde-ink">
        + {formatMoney(cobro.monto, "ARS")}
      </td>
      <td className="px-3 py-2 text-right text-xs text-muted-foreground">automático</td>
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
  const [beneficiario, setBeneficiario] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const cuentasQ = useQuery({
    queryKey: ["admin", "contabilidad", "cuentas-list"],
    queryFn: () => adminApi.listCuentas(),
  });
  const catsQ = useQuery({
    queryKey: ["admin", "contabilidad", "categorias"],
    queryFn: () => adminApi.listGastoCategorias(),
  });
  const benQ = useQuery({
    queryKey: ["admin", "contabilidad", "beneficiarios"],
    queryFn: () => adminApi.listBeneficiarios(),
  });

  const cuentas: Cuenta[] = cuentasQ.data?.cuentas ?? [];
  const categorias = catsQ.data?.categorias ?? [];
  const beneficiarios = benQ.data?.beneficiarios ?? [];

  // Una transferencia/ajuste no cruza monedas: el destino se limita a la moneda
  // del origen elegido (el backend igual lo valida).
  const monedaOrigen = cuentas.find((c) => String(c.id) === origen)?.moneda;
  const cuentasDestino = monedaOrigen ? cuentas.filter((c) => c.moneda === monedaOrigen) : cuentas;

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
    setBeneficiario("");
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
        beneficiario: beneficiario || null,
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
      <div className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
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
            {TIPO_MOVIMIENTO_META[t].label}
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
            <CuentaSelect cuentas={cuentasDestino} value={destino} onChange={setDestino} />
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
        <Field label="Beneficiario (opcional)">
          <input
            value={beneficiario}
            onChange={(e) => setBeneficiario(e.target.value)}
            list="benef-list"
            placeholder="Ej. Jimena (CM)"
            className="h-9 w-56 rounded-md border hairline bg-surface-elevated px-2 text-sm"
          />
          <datalist id="benef-list">
            {beneficiarios.map((b) => (
              <option key={b} value={b} />
            ))}
          </datalist>
        </Field>
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
      <span className="block font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}
