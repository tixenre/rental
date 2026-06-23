/**
 * RegistrarPagoModal — Modal para registrar un pago sobre un pedido.
 * Wired a adminApi.addPago(). Diseño según proto/app.jsx (PagoModal).
 */

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Label } from "@/design-system/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/design-system/ui/dialog";
import { cn } from "@/lib/utils";
import { adminApi, DESTINATARIOS_PAGO, METODOS_PAGO } from "@/lib/admin/api";
import { fmtArs } from "@/lib/format";

export function RegistrarPagoModal({
  pedidoId,
  total,
  pagado,
  open,
  onOpenChange,
}: {
  pedidoId: number;
  total: number;
  pagado: number;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const qc = useQueryClient();
  const saldo = Math.max(0, total - pagado);

  // Presets: Seña 50% / Saldo total / Otro
  type Preset = "sena" | "saldo" | "otro";
  const sena50 = Math.round(total * 0.5);

  const [preset, setPreset] = useState<Preset>(pagado === 0 ? "sena" : "saldo");
  const [montoInput, setMontoInput] = useState<string>(
    pagado === 0 ? String(sena50) : String(saldo),
  );
  const [concepto, setConcepto] = useState(pagado === 0 ? "Seña" : "Saldo final");
  // A quién se cobró y cómo. Default del dueño: Tincho + transferencia.
  const [destinatario, setDestinatario] = useState<string>("Rambla");
  const [metodo, setMetodo] = useState<string>("transferencia");

  const monto = Math.max(0, Number(montoInput) || 0);

  // Al abrir, re-inicializar contra el total/pagado ACTUALES (el pedido pudo
  // editarse desde que se montó el modal → los presets deben reflejar lo vigente).
  useEffect(() => {
    if (!open) return;
    setDestinatario("Tincho");
    setMetodo("transferencia");
    if (pagado === 0) {
      setPreset("sena");
      setMontoInput(String(Math.round(total * 0.5)));
      setConcepto("Seña");
    } else {
      setPreset("saldo");
      setMontoInput(String(Math.max(0, total - pagado)));
      setConcepto("Saldo final");
    }
  }, [open, total, pagado]);

  const selectPreset = (p: Preset) => {
    setPreset(p);
    if (p === "sena") {
      setMontoInput(String(sena50));
      setConcepto("Seña");
    } else if (p === "saldo") {
      setMontoInput(String(saldo));
      setConcepto("Saldo final");
    }
    // "otro" → deja el input libre
  };

  const handleMontoChange = (v: string) => {
    setMontoInput(v);
    const n = Number(v) || 0;
    // Si el monto editado a mano ya no coincide con los presets → "otro"
    if (n !== sena50 && n !== saldo) {
      setPreset("otro");
    } else if (n === sena50) {
      setPreset("sena");
    } else if (n === saldo) {
      setPreset("saldo");
    }
  };

  const addMut = useMutation({
    mutationFn: () =>
      adminApi.addPago(pedidoId, monto, concepto || undefined, undefined, destinatario, metodo),
    onSuccess: () => {
      toast.success("Pago registrado");
      qc.invalidateQueries({ queryKey: ["admin", "pedido", pedidoId] });
      qc.invalidateQueries({ queryKey: ["admin", "pedidos"] });
      qc.invalidateQueries({ queryKey: ["admin", "pagos-log"] });
      onOpenChange(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const progressPct = total > 0 ? Math.min(100, (pagado / total) * 100) : 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Registrar pago</DialogTitle>
        </DialogHeader>

        {/* Barra de progreso */}
        <div className="space-y-1">
          <div className="h-2 rounded-full bg-muted overflow-hidden">
            <div className="h-full bg-amber transition-all" style={{ width: `${progressPct}%` }} />
          </div>
          <div className="font-mono text-xs text-muted-foreground">
            {fmtArs(pagado)} de {fmtArs(total)} · resta {fmtArs(saldo)}
          </div>
        </div>

        {/* Presets */}
        <div className="flex gap-2">
          {(
            [
              ["sena", "Seña 50%"],
              ["saldo", "Saldo total"],
              ["otro", "Otro"],
            ] as [Preset, string][]
          ).map(([p, label]) => (
            <button
              key={p}
              type="button"
              onClick={() => selectPreset(p)}
              className={cn(
                "flex-1 rounded-md border px-2 py-1.5 text-xs font-medium transition",
                preset === p
                  ? "border-ink bg-ink text-background"
                  : "border-muted-foreground/30 text-muted-foreground hover:border-ink hover:text-ink",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Monto */}
        <div className="space-y-1">
          <Label className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
            Monto
          </Label>
          <div className="flex items-center gap-1.5 rounded-md border hairline bg-surface-elevated px-3 h-12">
            <span className="font-mono text-muted-foreground text-sm">$</span>
            <input
              type="number"
              min={0}
              value={montoInput}
              onChange={(e) => handleMontoChange(e.target.value)}
              className="flex-1 bg-transparent font-mono text-xl font-semibold tabular-nums focus:outline-none"
              placeholder="0"
            />
          </div>
        </div>

        {/* Concepto */}
        <div className="space-y-1">
          <Label
            htmlFor="pago-concepto"
            className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground"
          >
            Concepto
          </Label>
          <Input
            id="pago-concepto"
            value={concepto}
            onChange={(e) => setConcepto(e.target.value)}
            placeholder="Seña, saldo final…"
            className="h-9 text-sm"
          />
        </div>

        {/* Destinatario + método */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
              Cobró
            </Label>
            <div className="flex gap-1.5">
              {DESTINATARIOS_PAGO.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDestinatario(d)}
                  className={cn(
                    "flex-1 rounded-md border px-2 py-1.5 text-xs font-medium capitalize transition",
                    destinatario === d
                      ? "border-ink bg-ink text-background"
                      : "border-muted-foreground/30 text-muted-foreground hover:border-ink hover:text-ink",
                  )}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-1">
            <Label className="font-mono text-2xs uppercase tracking-[0.15em] text-muted-foreground">
              Método
            </Label>
            <div className="flex gap-1.5">
              {METODOS_PAGO.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMetodo(m)}
                  className={cn(
                    "flex-1 rounded-md border px-2 py-1.5 text-xs font-medium capitalize transition",
                    metodo === m
                      ? "border-ink bg-ink text-background"
                      : "border-muted-foreground/30 text-muted-foreground hover:border-ink hover:text-ink",
                  )}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* CTA */}
        <Button
          variant="amber"
          className="w-full"
          disabled={monto <= 0 || addMut.isPending}
          onClick={() => {
            if (!monto || monto <= 0) {
              toast.error("Ingresá un monto válido");
              return;
            }
            addMut.mutate();
          }}
        >
          {addMut.isPending ? "Registrando…" : `Cobrar ${fmtArs(monto)}`}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
