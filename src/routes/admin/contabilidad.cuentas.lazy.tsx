/**
 * contabilidad.cuentas.lazy.tsx — Cuentas/cajas con saldo (#809).
 *
 * Dos secciones, porque son dos cosas distintas:
 *  - **Socios · Cuenta corriente** (Pablo/Tincho): NO son cajas de plata, son el
 *    saldo de la rendición acumulada — DEUDOR (le debe a Rambla) / ACREEDOR (Rambla
 *    le debe). Sale de: arranque + cobró − su parte ± rendiciones.
 *  - **Cajas · Plata del negocio** (Efectivo/Banco/Fondo Rambla/Dólares…): plata
 *    real; suben/bajan con movimientos. Se pueden crear, editar y dar de baja.
 */
import { createLazyFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { adminApi, type CuentaSaldo, type TipoCuenta } from "@/lib/admin/api";
import { formatMoney } from "@/lib/format";
import { useDocumentTitle } from "@/lib/use-document-title";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// El socio se crea desde el sistema (seed); acá solo cajas/cuentas genéricas.
const TIPOS_CREABLES: TipoCuenta[] = ["caja", "banco", "fondo"];

export const Route = createLazyFileRoute("/admin/contabilidad/cuentas")({
  component: CuentasPage,
});

function CuentasPage() {
  useDocumentTitle("Cuentas · Finanzas");
  const qc = useQueryClient();

  const q = useQuery({
    queryKey: ["admin", "contabilidad", "saldos"],
    queryFn: () => adminApi.getSaldos(),
  });

  const invalidar = () => qc.invalidateQueries({ queryKey: ["admin", "contabilidad"] });

  const socios = q.data?.socios ?? [];
  const cajas = q.data?.cajas ?? [];

  return (
    <div className="px-4 md:px-6 py-6 space-y-8 max-w-4xl mx-auto">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Back-office · Finanzas
          </div>
          <h1 className="font-display text-3xl text-ink">Cuentas</h1>
          <p className="text-sm text-muted-foreground mt-1">
            La cuenta corriente de cada socio (quién le debe a quién) y las cajas con la plata real
            del negocio.
          </p>
        </div>
        <Link
          to="/admin/contabilidad"
          className="shrink-0 h-9 rounded-md border hairline px-3 text-sm flex items-center hover:bg-muted/40"
        >
          ← Tablero
        </Link>
      </header>

      {q.isLoading && <div className="text-sm text-muted-foreground">Cargando cuentas…</div>}
      {q.isError && (
        <div className="text-sm text-destructive">
          Error cargando las cuentas. {(q.error as Error)?.message}
        </div>
      )}

      {/* Socios · Cuenta corriente */}
      {socios.length > 0 && (
        <section className="space-y-3">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Socios · Cuenta corriente
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {socios.map((s) => (
              <SocioCard key={s.id} socio={s} cajas={cajas} onChanged={invalidar} />
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            El <strong>arranque</strong> es lo que cobró antes del sistema. Se va saldando con{" "}
            <strong>su parte</strong> de lo que se alquila: cuando llega a cero están a mano, y si
            se da vuelta, Rambla le debe a él.
          </p>
        </section>
      )}

      {/* Cajas · Plata del negocio */}
      {q.data && (
        <section className="space-y-3">
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Cajas · Plata del negocio
          </div>
          <div className="overflow-x-auto rounded-lg border hairline">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b hairline text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Caja</th>
                  <th className="px-3 py-2 font-medium">Tipo</th>
                  <th className="px-3 py-2 font-medium text-right">Saldo inicial</th>
                  <th className="px-3 py-2 font-medium text-right">Saldo actual</th>
                  <th className="px-3 py-2 font-medium text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {cajas.map((c) => (
                  <CajaRow key={c.id} cuenta={c} onChanged={invalidar} />
                ))}
              </tbody>
              <tfoot>
                {Object.entries(q.data.totales)
                  .sort(([a], [b]) => (a === "ARS" ? -1 : b === "ARS" ? 1 : a.localeCompare(b)))
                  .map(([moneda, total]) => (
                    <tr key={moneda} className="border-t hairline">
                      <td className="px-3 py-2 font-medium" colSpan={3}>
                        Total disponible {moneda !== "ARS" ? `(${moneda})` : ""}
                      </td>
                      <td className="px-3 py-2 text-right font-mono font-semibold tabular-nums">
                        {formatMoney(total, moneda)}
                      </td>
                      <td />
                    </tr>
                  ))}
              </tfoot>
            </table>
          </div>
        </section>
      )}

      <NuevaCuentaForm onCreated={invalidar} />
    </div>
  );
}

function SocioCard({
  socio,
  cajas,
  onChanged,
}: {
  socio: CuentaSaldo;
  cajas: CuentaSaldo[];
  onChanged: () => void;
}) {
  const [editando, setEditando] = useState(false);
  const [arranque, setArranque] = useState(String(socio.saldo_inicial));

  // Cajas de la misma moneda que el socio (la transferencia no mezcla monedas).
  const cajasMov = cajas.filter((c) => c.moneda === socio.moneda);
  const [movAbierto, setMovAbierto] = useState(false);
  const [dir, setDir] = useState<"pago" | "cargo">("pago");
  const [montoMov, setMontoMov] = useState("");
  const [cajaId, setCajaId] = useState<number | "">("");
  const [notaMov, setNotaMov] = useState("");

  const cerrarMov = () => {
    setMovAbierto(false);
    setMontoMov("");
    setCajaId("");
    setNotaMov("");
    setDir("pago");
  };

  const registrarMov = useMutation({
    mutationFn: () => {
      const monto = Number(montoMov) || 0;
      const caja = Number(cajaId);
      // pago/rindió: el socio entrega → sale de su cuenta, entra a la caja (baja deuda).
      // cargo: Rambla puso por él → sale de la caja, entra a su cuenta (sube deuda).
      const origen = dir === "pago" ? socio.id : caja;
      const destino = dir === "pago" ? caja : socio.id;
      return adminApi.createMovimiento({
        tipo: "transferencia",
        monto,
        cuenta_origen_id: origen,
        cuenta_destino_id: destino,
        nota: notaMov.trim() || null,
      });
    },
    onSuccess: () => {
      cerrarMov();
      toast.success(dir === "pago" ? "Pago registrado" : "Cargo registrado");
      onChanged();
    },
    onError: (e) => toast.error("No se pudo registrar", { description: (e as Error).message }),
  });

  const guardar = useMutation({
    mutationFn: () => adminApi.updateCuenta(socio.id, { saldo_inicial: Number(arranque) || 0 }),
    onSuccess: () => {
      setEditando(false);
      toast.success("Arranque actualizado");
      onChanged();
    },
    onError: (e) => toast.error("No se pudo actualizar", { description: (e as Error).message }),
  });

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
  const tag =
    socio.estado === "deudor" ? "Deudor" : socio.estado === "acreedor" ? "Acreedor" : "Saldado";
  const tagColor =
    socio.estado === "deudor"
      ? "bg-destructive/10 text-destructive"
      : socio.estado === "acreedor"
        ? "bg-verde/10 text-verde"
        : "bg-muted text-muted-foreground";

  return (
    <div className="rounded-lg border hairline p-4 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="font-medium text-ink">{socio.nombre}</div>
        <span
          className={cn(
            "font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full",
            tagColor,
          )}
        >
          {tag}
        </span>
      </div>
      <div className={cn("font-mono text-2xl font-semibold tabular-nums", color)}>
        {formatMoney(abs, socio.moneda)}
      </div>
      <div className="text-sm text-muted-foreground">{frase}</div>
      <div className="font-mono text-[11px] text-muted-foreground tabular-nums">
        arranque {formatMoney(socio.saldo_inicial, socio.moneda)} · cobró{" "}
        {formatMoney(socio.ingresos_alquiler, socio.moneda)} · su parte{" "}
        {formatMoney(socio.su_parte, socio.moneda)}
      </div>
      {editando ? (
        <div className="flex items-center gap-1 pt-1">
          <input
            type="number"
            value={arranque}
            onChange={(e) => setArranque(e.target.value)}
            className="h-8 w-32 rounded-md border hairline bg-surface-elevated px-2 text-right text-sm tabular-nums"
            aria-label="Arranque"
          />
          <button
            type="button"
            onClick={() => guardar.mutate()}
            disabled={guardar.isPending}
            className="h-8 rounded-md bg-ink px-2 text-xs text-background disabled:opacity-50"
          >
            Guardar
          </button>
          <button
            type="button"
            onClick={() => {
              setEditando(false);
              setArranque(String(socio.saldo_inicial));
            }}
            className="h-8 rounded-md border hairline px-2 text-xs"
          >
            Cancelar
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setMovAbierto((v) => !v)}
            className="text-xs text-ink underline hover:text-amber"
          >
            Registrar movimiento
          </button>
          <button
            type="button"
            onClick={() => setEditando(true)}
            className="text-xs text-muted-foreground underline hover:text-amber"
            title="Editar el arranque (lo que cobró antes del sistema)"
          >
            Editar arranque
          </button>
        </div>
      )}

      {movAbierto && (
        <div className="pt-2 mt-1 border-t hairline space-y-2">
          <div className="flex gap-1">
            {(["pago", "cargo"] as const).map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDir(d)}
                className={cn(
                  "flex-1 rounded-md border px-2 py-1.5 text-xs font-medium transition",
                  dir === d
                    ? "border-ink bg-ink text-background"
                    : "border-muted-foreground/30 text-muted-foreground hover:border-ink",
                )}
              >
                {d === "pago" ? "Me pagó / rindió" : "Le cargué"}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground">
            {dir === "pago"
              ? `${socio.nombre} entrega plata → baja su deuda y entra a la caja.`
              : `Rambla puso plata por ${socio.nombre} (ej. le compró algo) → sube su deuda y sale de la caja.`}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="number"
              value={montoMov}
              onChange={(e) => setMontoMov(e.target.value)}
              placeholder="Monto"
              className="h-8 w-28 rounded-md border hairline bg-surface-elevated px-2 text-right text-sm tabular-nums"
            />
            <select
              value={cajaId}
              onChange={(e) => setCajaId(e.target.value ? Number(e.target.value) : "")}
              className="h-8 rounded-md border hairline bg-surface-elevated px-2 text-sm"
            >
              <option value="">{dir === "pago" ? "¿A qué caja?" : "¿De qué caja?"}</option>
              {cajasMov.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </select>
          </div>
          <input
            value={notaMov}
            onChange={(e) => setNotaMov(e.target.value)}
            placeholder="Nota (ej. adaptador de lente)"
            className="h-8 w-full rounded-md border hairline bg-surface-elevated px-2 text-sm"
          />
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => registrarMov.mutate()}
              disabled={registrarMov.isPending || !(Number(montoMov) > 0) || !cajaId}
              className="h-8 rounded-md bg-ink px-3 text-xs text-background disabled:opacity-50"
            >
              Registrar
            </button>
            <button
              type="button"
              onClick={cerrarMov}
              className="h-8 rounded-md border hairline px-2 text-xs"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function CajaRow({ cuenta, onChanged }: { cuenta: CuentaSaldo; onChanged: () => void }) {
  const [editando, setEditando] = useState(false);
  const [nombre, setNombre] = useState(cuenta.nombre);
  const [valor, setValor] = useState(String(cuenta.saldo_inicial));

  const cerrar = () => {
    setEditando(false);
    setNombre(cuenta.nombre);
    setValor(String(cuenta.saldo_inicial));
  };

  const guardar = useMutation({
    mutationFn: () =>
      adminApi.updateCuenta(cuenta.id, {
        nombre: nombre.trim(),
        saldo_inicial: Number(valor) || 0,
      }),
    onSuccess: () => {
      setEditando(false);
      toast.success("Cuenta actualizada");
      onChanged();
    },
    onError: (e) => toast.error("No se pudo actualizar", { description: (e as Error).message }),
  });

  const baja = useMutation({
    mutationFn: () => adminApi.deactivateCuenta(cuenta.id),
    onSuccess: () => {
      toast.success("Cuenta dada de baja");
      onChanged();
    },
    onError: (e) => toast.error("No se pudo dar de baja", { description: (e as Error).message }),
  });

  // El Fondo Rambla representa al cobrador Rambla: recibe cobros, no se da de baja.
  const esCobrador = Boolean(cuenta.socio);

  return (
    <tr className="border-b hairline last:border-0">
      <td className="px-3 py-2 font-medium text-ink">
        {editando ? (
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            className="h-8 w-44 rounded-md border hairline bg-surface-elevated px-2 text-sm"
          />
        ) : (
          cuenta.nombre
        )}
      </td>
      <td className="px-3 py-2">
        <Badge variant="secondary" className="capitalize">
          {cuenta.tipo}
        </Badge>
      </td>
      <td className="px-3 py-2 text-right">
        {editando ? (
          <input
            type="number"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
            className="h-8 w-28 rounded-md border hairline bg-surface-elevated px-2 text-right text-sm tabular-nums"
          />
        ) : (
          <span className="font-mono tabular-nums">
            {formatMoney(cuenta.saldo_inicial, cuenta.moneda)}
          </span>
        )}
      </td>
      <td className="px-3 py-2 text-right font-mono font-semibold tabular-nums">
        {formatMoney(cuenta.saldo, cuenta.moneda)}
      </td>
      <td className="px-3 py-2 text-right">
        {editando ? (
          <div className="flex items-center justify-end gap-1">
            <button
              type="button"
              onClick={() => guardar.mutate()}
              disabled={guardar.isPending || !nombre.trim()}
              className="h-8 rounded-md bg-ink px-2 text-xs text-background disabled:opacity-50"
            >
              Guardar
            </button>
            <button
              type="button"
              onClick={cerrar}
              className="h-8 rounded-md border hairline px-2 text-xs"
            >
              Cancelar
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={() => setEditando(true)}
              className="text-xs text-muted-foreground underline hover:text-amber"
              title="Editar nombre y saldo inicial"
            >
              Editar
            </button>
            <button
              type="button"
              onClick={() => {
                if (
                  window.confirm(
                    `¿Dar de baja "${cuenta.nombre}"? Solo se puede si su saldo es cero.`,
                  )
                )
                  baja.mutate();
              }}
              disabled={baja.isPending || esCobrador}
              className={cn(
                "text-xs underline",
                esCobrador
                  ? "text-muted-foreground/40 cursor-not-allowed no-underline"
                  : "text-muted-foreground hover:text-destructive",
              )}
              title={esCobrador ? "El Fondo Rambla no se da de baja" : "Dar de baja"}
            >
              Baja
            </button>
          </div>
        )}
      </td>
    </tr>
  );
}

function NuevaCuentaForm({ onCreated }: { onCreated: () => void }) {
  const [nombre, setNombre] = useState("");
  const [tipo, setTipo] = useState<TipoCuenta>("caja");
  const [moneda, setMoneda] = useState("ARS");
  const [saldoInicial, setSaldoInicial] = useState("0");

  const crear = useMutation({
    mutationFn: () =>
      adminApi.createCuenta({
        nombre: nombre.trim(),
        tipo,
        moneda,
        saldo_inicial: Number(saldoInicial) || 0,
      }),
    onSuccess: () => {
      setNombre("");
      setSaldoInicial("0");
      setTipo("caja");
      setMoneda("ARS");
      toast.success("Cuenta creada");
      onCreated();
    },
    onError: (e) =>
      toast.error("No se pudo crear la cuenta", { description: (e as Error).message }),
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!nombre.trim()) return;
        crear.mutate();
      }}
      className="rounded-lg border hairline p-4 space-y-3"
    >
      <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
        Nueva caja
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="space-y-1">
          <span className="block font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Nombre
          </span>
          <input
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="Ej. Mercado Pago"
            className="h-9 w-48 rounded-md border hairline bg-surface-elevated px-2 text-sm"
          />
        </label>
        <label className="space-y-1">
          <span className="block font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Tipo
          </span>
          <select
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoCuenta)}
            className="h-9 rounded-md border hairline bg-surface-elevated px-2 text-sm capitalize"
          >
            {TIPOS_CREABLES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="block font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Moneda
          </span>
          <select
            value={moneda}
            onChange={(e) => setMoneda(e.target.value)}
            className="h-9 rounded-md border hairline bg-surface-elevated px-2 text-sm"
          >
            <option value="ARS">Pesos (ARS)</option>
            <option value="USD">Dólares (USD)</option>
          </select>
        </label>
        <label className="space-y-1">
          <span className="block font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
            Saldo inicial
          </span>
          <input
            type="number"
            value={saldoInicial}
            onChange={(e) => setSaldoInicial(e.target.value)}
            className="h-9 w-32 rounded-md border hairline bg-surface-elevated px-2 text-right text-sm tabular-nums"
          />
        </label>
        <button
          type="submit"
          disabled={crear.isPending || !nombre.trim()}
          className="h-9 rounded-md bg-ink px-4 text-sm text-background disabled:opacity-50"
        >
          {crear.isPending ? "Creando…" : "Crear"}
        </button>
      </div>
    </form>
  );
}
