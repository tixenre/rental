import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";

import { adminApi } from "@/lib/admin/api";

/**
 * LeadTimeSection — antelación mínima (lead-time) para reservar online (#1126).
 *
 * Horas mínimas entre que el cliente hace el pedido y el retiro. Con valor > 0,
 * un pedido dentro de esa ventana se bloquea online y la web le muestra un
 * disclaimer para coordinar la urgencia por WhatsApp. 0 = apagado. El admin
 * nunca queda limitado por esto (carga urgencias a mano desde el back-office).
 */
export function LeadTimeSection() {
  const qc = useQueryClient();
  const [valor, setValor] = useState("");

  const settingQ = useQuery({
    queryKey: ["settings", "antelacion_minima_horas"],
    queryFn: () => adminApi.getSetting("antelacion_minima_horas"),
    staleTime: 0,
  });

  useEffect(() => {
    if (settingQ.data && valor === "") setValor(settingQ.data.value ?? "0");
  }, [settingQ.data, valor]);

  const updateMut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting("antelacion_minima_horas", v),
    onSuccess: () => {
      toast.success("Antelación mínima actualizada");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const actual = settingQ.data?.value ?? "0";
  const dirty = valor.trim() !== actual && valor.trim() !== "";

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Antelación mínima (lead-time)</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Horas mínimas entre el pedido y el retiro para reservar online. Dentro de esa ventana el
          cliente no puede confirmar por la web (ve un aviso para coordinar la urgencia por
          WhatsApp; aunque figure stock, no se garantiza — cada pedido se revisa a mano). Poné 0
          para desactivarlo. Ej: 12 = medio día. El admin nunca queda limitado.
        </p>
      </div>
      <div className="flex items-end gap-2 border-t hairline pt-3">
        <div className="space-y-1">
          <div className="text-2xs uppercase tracking-wide text-muted-foreground">
            Horas de antelación
          </div>
          <Input
            type="number"
            min={0}
            className="w-28"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
          />
        </div>
        <Button
          size="sm"
          onClick={() => updateMut.mutate(String(Math.max(0, Math.floor(Number(valor) || 0))))}
          disabled={!dirty || updateMut.isPending}
        >
          {updateMut.isPending ? "Guardando…" : "Guardar"}
        </Button>
      </div>
    </section>
  );
}
