import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";

import { adminApi } from "@/lib/admin/api";

const DIAS_ORDEN: Array<[string, string]> = [
  ["lun", "Lunes"],
  ["mar", "Martes"],
  ["mie", "Miércoles"],
  ["jue", "Jueves"],
  ["vie", "Viernes"],
  ["sab", "Sábado"],
  ["dom", "Domingo"],
];
type DiaCfg = { abierto: boolean; desde: string; hasta: string };
const DEFAULT_DIA: DiaCfg = { abierto: true, desde: "09:00", hasta: "18:00" };

export function HorariosSection() {
  const qc = useQueryClient();
  const [cfg, setCfg] = useState<Record<string, DiaCfg> | null>(null);

  const settingQ = useQuery({
    queryKey: ["settings", "horarios_retiro"],
    queryFn: () => adminApi.getSetting("horarios_retiro"),
    retry: false,
    staleTime: 60_000,
  });

  // Inicializa el estado desde el setting (o defaults: L-V abierto, finde
  // cerrado). Espera a que el fetch termine (isFetched) para no pisar el valor
  // guardado con los defaults.
  useEffect(() => {
    if (cfg !== null || !settingQ.isFetched) return;
    let parsed: Record<string, { desde: string; hasta: string } | null> = {};
    try {
      parsed = settingQ.data?.value ? JSON.parse(settingQ.data.value) : {};
    } catch {
      parsed = {};
    }
    const hasData = Object.keys(parsed).length > 0;
    const next: Record<string, DiaCfg> = {};
    for (const [key] of DIAS_ORDEN) {
      const f = parsed[key];
      if (hasData) {
        next[key] = f
          ? { abierto: true, desde: f.desde, hasta: f.hasta }
          : { ...DEFAULT_DIA, abierto: false };
      } else {
        // Sin config previa: plantilla L-V abierto 09-18, finde cerrado.
        next[key] =
          key === "sab" || key === "dom" ? { ...DEFAULT_DIA, abierto: false } : { ...DEFAULT_DIA };
      }
    }
    setCfg(next);
  }, [settingQ.data, settingQ.isFetched, cfg]);

  const updateMut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting("horarios_retiro", v),
    onSuccess: () => {
      toast.success("Horarios actualizados");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const setDia = (key: string, patch: Partial<DiaCfg>) =>
    setCfg((prev) => (prev ? { ...prev, [key]: { ...prev[key], ...patch } } : prev));

  const save = () => {
    if (!cfg) return;
    const payload: Record<string, { desde: string; hasta: string } | null> = {};
    for (const [key] of DIAS_ORDEN) {
      const d = cfg[key];
      if (d.abierto && d.desde >= d.hasta) {
        toast.error(
          `${DIAS_ORDEN.find(([k]) => k === key)?.[1]}: la apertura debe ser anterior al cierre`,
        );
        return;
      }
      payload[key] = d.abierto ? { desde: d.desde, hasta: d.hasta } : null;
    }
    updateMut.mutate(JSON.stringify(payload));
  };

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Horarios de retiro y devolución</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Franja horaria habilitada por día para que el cliente elija retiro y devolución (misma
          franja para ambos). Los días cerrados no se pueden seleccionar. Aplica al checkout del
          cliente — los pedidos cargados a mano en el back-office no se restringen.
        </p>
      </div>
      <div className="border-t hairline pt-3 space-y-2">
        {cfg &&
          DIAS_ORDEN.map(([key, label]) => {
            const d = cfg[key];
            return (
              <div key={key} className="flex items-center gap-3">
                <label className="flex items-center gap-2 w-40 shrink-0 text-sm">
                  {/* eslint-disable-next-line no-restricted-syntax -- checkbox nativo: el DS Checkbox es Radix (otra API) */}
                  <input
                    type="checkbox"
                    checked={d.abierto}
                    onChange={(e) => setDia(key, { abierto: e.target.checked })}
                  />
                  <span className={d.abierto ? "text-ink" : "text-muted-foreground line-through"}>
                    {label}
                  </span>
                </label>
                {d.abierto ? (
                  <div className="flex items-center gap-1.5 text-sm">
                    <Input
                      type="time"
                      step={1800}
                      value={d.desde}
                      onChange={(e) => setDia(key, { desde: e.target.value })}
                      className="w-28"
                    />
                    <span className="text-muted-foreground">–</span>
                    <Input
                      type="time"
                      step={1800}
                      value={d.hasta}
                      onChange={(e) => setDia(key, { hasta: e.target.value })}
                      className="w-28"
                    />
                  </div>
                ) : (
                  <span className="text-xs text-muted-foreground italic">Cerrado</span>
                )}
              </div>
            );
          })}
        <div className="pt-2">
          <Button size="sm" onClick={save} disabled={!cfg || updateMut.isPending}>
            {updateMut.isPending ? "Guardando…" : "Guardar horarios"}
          </Button>
        </div>
      </div>
    </section>
  );
}
