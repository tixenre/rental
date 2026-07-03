import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";

import { adminApi } from "@/lib/admin/api";

export function BufferSection() {
  const qc = useQueryClient();
  const [valor, setValor] = useState("");

  const settingQ = useQuery({
    queryKey: ["settings", "buffer_horas_alquiler"],
    queryFn: () => adminApi.getSetting("buffer_horas_alquiler"),
    staleTime: 0,
  });

  useEffect(() => {
    if (settingQ.data && valor === "") setValor(settingQ.data.value ?? "0");
  }, [settingQ.data, valor]);

  const updateMut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting("buffer_horas_alquiler", v),
    onSuccess: () => {
      toast.success("Buffer actualizado");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const actual = settingQ.data?.value ?? "0";
  const dirty = valor.trim() !== actual && valor.trim() !== "";

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Buffer entre alquileres</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Horas de prep/revisión exigidas entre que un equipo vuelve y sale de nuevo. Con buffer
          &gt; 0, dos alquileres del mismo equipo no pueden quedar pegados (respeta la hora de
          retiro/devolución). Poné 0 para permitir alquileres consecutivos. Ej: 24 = un día.
        </p>
      </div>
      <div className="flex items-end gap-2 border-t hairline pt-3">
        <div className="space-y-1">
          <div className="text-2xs uppercase tracking-wide text-muted-foreground">
            Horas de buffer
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
