/**
 * CambioDivisaForm.tsx — comprar/vender divisa (hoy ARS↔USD) con la caja de
 * otra moneda. Registra el par de `ajuste` atados de
 * `contabilidad/commands/movimientos.py::crear_cambio_divisa` — NO afecta la
 * ganancia del mes (no es `gasto`).
 *
 * Dos modos de carga (según qué dato tenga el dueño a mano):
 * - "Tengo la cotización": pone el monto en la moneda de origen + la
 *   cotización → el monto en la otra moneda se calcula solo.
 * - "Tengo los dos montos": pone ambos montos → la cotización se calcula sola.
 * Funciona en cualquier dirección (comprar o vender) según qué cuenta se
 * elija como origen/destino — el cálculo del preview es el mismo.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { adminApi, type Cuenta } from "@/lib/admin/api";
import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import { CuentaSelect, Field } from "@/components/admin/contabilidad/fields";

type Modo = "cotizacion" | "montos";

/** Preview client-side, espeja `derivar_cambio_divisa` (backend) — la cotización
 * es siempre "pesos por dólar", sin importar cuál lado es origen/destino. El
 * backend es la fuente de verdad (revalida todo); esto es solo para mostrar
 * el número mientras se completa el form. */
function derivarPreview(
  monedaOrigen: string | undefined,
  monedaDestino: string | undefined,
  montoOrigen: number | null,
  montoDestino: number | null,
  cotizacion: number | null,
): { montoDestinoCalc: number | null; cotizacionCalc: number | null } {
  if (!monedaOrigen || !monedaDestino || monedaOrigen === monedaDestino) {
    return { montoDestinoCalc: null, cotizacionCalc: null };
  }
  const ladoArsEsOrigen = monedaOrigen === "ARS";
  const montoArs = ladoArsEsOrigen ? montoOrigen : montoDestino;
  const montoDivisaConocido = ladoArsEsOrigen ? montoDestino : montoOrigen;

  if (montoArs != null && montoArs > 0 && montoDivisaConocido != null && montoDivisaConocido > 0) {
    return {
      montoDestinoCalc: null,
      cotizacionCalc: Math.round((montoArs / montoDivisaConocido) * 10000) / 10000,
    };
  }
  if (montoArs != null && montoArs > 0 && cotizacion != null && cotizacion > 0) {
    const montoDivisa = Math.round(montoArs / cotizacion);
    return { montoDestinoCalc: ladoArsEsOrigen ? montoDivisa : montoArs, cotizacionCalc: null };
  }
  return { montoDestinoCalc: null, cotizacionCalc: null };
}

export function CambioDivisaForm({ onCreated }: { onCreated: () => void }) {
  const [origen, setOrigen] = useState("");
  const [destino, setDestino] = useState("");
  const [modo, setModo] = useState<Modo>("cotizacion");
  const [montoOrigenStr, setMontoOrigenStr] = useState("");
  const [montoDestinoStr, setMontoDestinoStr] = useState("");
  const [cotizacionStr, setCotizacionStr] = useState("");
  const [fecha, setFecha] = useState("");
  const [nota, setNota] = useState("");

  const cuentasQ = useQuery({
    queryKey: ["admin", "contabilidad", "cuentas-list"],
    queryFn: () => adminApi.listCuentas(),
  });
  const cuentas: Cuenta[] = cuentasQ.data?.cuentas ?? [];

  const cuentaOrigen = cuentas.find((c) => String(c.id) === origen);
  const cuentaDestino = cuentas.find((c) => String(c.id) === destino);
  // El destino tiene que ser de otra moneda (si no, es una transferencia común).
  const cuentasDestino = cuentaOrigen
    ? cuentas.filter((c) => c.moneda !== cuentaOrigen.moneda)
    : cuentas;

  const montoOrigen = montoOrigenStr ? Number(montoOrigenStr) : null;
  const montoDestino = modo === "montos" && montoDestinoStr ? Number(montoDestinoStr) : null;
  const cotizacionInput = modo === "cotizacion" && cotizacionStr ? Number(cotizacionStr) : null;

  const preview = useMemo(
    () =>
      derivarPreview(
        cuentaOrigen?.moneda,
        cuentaDestino?.moneda,
        montoOrigen,
        montoDestino,
        cotizacionInput,
      ),
    [cuentaOrigen?.moneda, cuentaDestino?.moneda, montoOrigen, montoDestino, cotizacionInput],
  );

  const reset = () => {
    setMontoOrigenStr("");
    setMontoDestinoStr("");
    setCotizacionStr("");
    setFecha("");
    setNota("");
  };

  const crear = useMutation({
    mutationFn: () =>
      adminApi.createCambioDivisa({
        cuenta_origen_id: Number(origen),
        cuenta_destino_id: Number(destino),
        monto_origen: montoOrigen,
        monto_destino: modo === "montos" ? montoDestino : null,
        cotizacion: modo === "cotizacion" ? cotizacionInput : null,
        fecha: fecha || null,
        nota: nota || null,
      }),
    onSuccess: (r) => {
      reset();
      toast.success(
        `Cambio registrado: ${formatMoney(r.origen.monto, r.origen.moneda)} → ${formatMoney(r.destino.monto, r.destino.moneda)}`,
      );
      onCreated();
    },
    onError: (e) => toast.error("No se pudo registrar", { description: (e as Error).message }),
  });

  const valido =
    !!origen &&
    !!destino &&
    origen !== destino &&
    !!montoOrigen &&
    montoOrigen > 0 &&
    ((modo === "cotizacion" && !!cotizacionInput && cotizacionInput > 0) ||
      (modo === "montos" && !!montoDestino && montoDestino > 0));

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!valido) {
          toast.error("Completá cuenta origen, cuenta destino y los montos/cotización");
          return;
        }
        crear.mutate();
      }}
      className="rounded-lg border hairline p-4 space-y-3"
    >
      <div className="t-eyebrow">Cambio de divisa</div>
      <p className="text-xs text-muted-foreground">
        Comprar o vender dólares con pesos: se registran dos ajustes atados, uno por caja. No es
        ganancia ni gasto — solo cambia de forma tu plata.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <Field label="Sale de">
          <CuentaSelect
            cuentas={cuentas}
            value={origen}
            onChange={(v) => {
              setOrigen(v);
              if (v === destino) setDestino("");
            }}
          />
        </Field>
        <Field label="Entra a">
          <CuentaSelect cuentas={cuentasDestino} value={destino} onChange={setDestino} />
        </Field>
        <Field label="Fecha">
          <Input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
        </Field>
      </div>

      <div className="flex flex-wrap gap-1">
        {(
          [
            ["cotizacion", "Tengo la cotización"],
            ["montos", "Tengo los dos montos"],
          ] as const
        ).map(([val, lbl]) => (
          <button
            key={val}
            type="button"
            onClick={() => setModo(val)}
            className={cn(
              "rounded-md border px-2.5 py-1.5 text-xs font-medium transition",
              modo === val
                ? "border-ink bg-ink text-background"
                : "border-muted-foreground/30 text-muted-foreground hover:border-ink hover:text-ink",
            )}
          >
            {lbl}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Field label={`Monto en ${cuentaOrigen?.moneda ?? "origen"}`}>
          <Input
            type="number"
            value={montoOrigenStr}
            onChange={(e) => setMontoOrigenStr(e.target.value)}
            className="w-36 text-right tabular-nums"
          />
        </Field>

        {modo === "cotizacion" ? (
          <>
            <Field label="Cotización ($ por dólar)">
              <Input
                type="number"
                value={cotizacionStr}
                onChange={(e) => setCotizacionStr(e.target.value)}
                className="w-36 text-right tabular-nums"
              />
            </Field>
            {preview.montoDestinoCalc != null && (
              <div className="text-xs text-muted-foreground">
                = {formatMoney(preview.montoDestinoCalc, cuentaDestino?.moneda)} en{" "}
                {cuentaDestino?.nombre ?? "destino"}
              </div>
            )}
          </>
        ) : (
          <>
            <Field label={`Monto en ${cuentaDestino?.moneda ?? "destino"}`}>
              <Input
                type="number"
                value={montoDestinoStr}
                onChange={(e) => setMontoDestinoStr(e.target.value)}
                className="w-36 text-right tabular-nums"
              />
            </Field>
            {preview.cotizacionCalc != null && (
              <div className="text-xs text-muted-foreground">
                = cotización {preview.cotizacionCalc}
              </div>
            )}
          </>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Field label="Nota (opcional)">
          <Input
            value={nota}
            onChange={(e) => setNota(e.target.value)}
            placeholder="Ej. casa de cambio X"
            className="w-64"
          />
        </Field>
        <Button
          type="submit"
          variant="primary"
          disabled={crear.isPending}
          loading={crear.isPending}
        >
          {crear.isPending ? "Guardando…" : "Registrar cambio"}
        </Button>
      </div>
    </form>
  );
}
