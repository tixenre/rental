import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { adminApi } from "@/lib/admin/api";

export function GoogleAnalyticsSection() {
  const qc = useQueryClient();
  const [valor, setValor] = useState("");
  const [cargado, setCargado] = useState(false);

  // getSetting devuelve 404 si nunca se configuró → lo tratamos como vacío
  // (GA apagado), sin reintentar ni mostrar error.
  const settingQ = useQuery({
    queryKey: ["settings", "ga4_measurement_id"],
    queryFn: () => adminApi.getSetting("ga4_measurement_id"),
    staleTime: 60_000,
    retry: false,
  });

  useEffect(() => {
    if (!cargado && (settingQ.isSuccess || settingQ.isError)) {
      setValor(settingQ.data?.value ?? "");
      setCargado(true);
    }
  }, [cargado, settingQ.isSuccess, settingQ.isError, settingQ.data]);

  const actual = (settingQ.data?.value ?? "").toUpperCase();

  const updateMut = useMutation({
    mutationFn: (v: string) => adminApi.updateSetting("ga4_measurement_id", v),
    onSuccess: (_d, v) => {
      toast.success(v.trim() ? "Google Analytics activado" : "Google Analytics desactivado");
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const norm = valor.trim().toUpperCase();
  const dirty = norm !== actual;

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Google Analytics</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Pegá el <strong>Measurement ID</strong> de tu propiedad de Google Analytics (formato{" "}
          <code className="text-[11px]">G-XXXXXXXXXX</code>) para medir el tráfico del catálogo
          público. Lo sacás de Google Analytics → Admin → Flujos de datos → Web. Dejalo vacío para
          apagar la medición.
        </p>
        <p className="text-[11px] text-muted-foreground mt-1">
          Solo mide el catálogo público (el back-office y el portal de clientes quedan afuera). La
          medición se activa únicamente en el sitio real de producción; en el ambiente de prueba no
          corre, para no ensuciar los datos.
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-2 border-t hairline pt-3">
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Measurement ID
          </div>
          <Input
            placeholder="G-XXXXXXXXXX"
            className="w-56 font-mono"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
          />
        </div>
        <Button
          size="sm"
          onClick={() => updateMut.mutate(norm)}
          disabled={!dirty || updateMut.isPending}
        >
          {updateMut.isPending ? "Guardando…" : "Guardar"}
        </Button>
        {actual && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setValor("");
              updateMut.mutate("");
            }}
            disabled={updateMut.isPending}
          >
            Quitar
          </Button>
        )}
      </div>
    </section>
  );
}
