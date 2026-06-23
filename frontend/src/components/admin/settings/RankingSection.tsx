import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";

import { adminApi } from "@/lib/admin/api";

export function RankingSection() {
  const qc = useQueryClient();
  const [reporte, setReporte] = useState<Awaited<
    ReturnType<typeof adminApi.recalcularRanking>
  > | null>(null);

  const recalcMut = useMutation({
    mutationFn: (dry_run: boolean) => adminApi.recalcularRanking({ dry_run, ventana_dias: 180 }),
    onSuccess: (data) => {
      setReporte(data);
      if (!data.dry_run) {
        toast.success(`Ranking recalculado · ${data.cambios.length} equipos actualizados`);
        qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
        qc.invalidateQueries({ queryKey: ["equipos"] });
      } else {
        toast.message(`Preview: ${data.cambios.length} equipos cambiarían (dry-run)`);
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-amber" /> Ranking automático
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Calcula la prioridad de cada equipo en el catálogo basándose en el histórico de pedidos e
          ingresos de los últimos 180 días. Normalizado por categoría (los equipos compiten contra
          sus pares, no contra todo el inventario).
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-2 pt-2">
        <Button
          variant="outline"
          onClick={() => recalcMut.mutate(true)}
          disabled={recalcMut.isPending}
        >
          {recalcMut.isPending && recalcMut.variables ? (
            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
          ) : null}
          Ver preview (dry-run)
        </Button>
        <Button onClick={() => recalcMut.mutate(false)} disabled={recalcMut.isPending}>
          {recalcMut.isPending && !recalcMut.variables ? (
            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
          ) : null}
          Recalcular y aplicar
        </Button>
      </div>

      {reporte && (
        <div className="mt-3 space-y-2 rounded-md border hairline bg-muted/30 p-3">
          <div className="text-xs">
            <span className="font-medium text-ink">
              {reporte.dry_run ? "Preview (dry-run): " : "Aplicado: "}
            </span>
            <span className="text-muted-foreground">
              {reporte.cambios.length} equipos {reporte.dry_run ? "cambiarían" : "actualizados"},{" "}
              {reporte.sin_cambios} sin cambios. Ventana: {reporte.ventana_dias} días.
            </span>
          </div>
          {reporte.cambios.length > 0 && (
            <div className="space-y-1 max-h-80 overflow-y-auto">
              {reporte.cambios
                .slice()
                .sort((a, b) => b.despues.score - b.antes.score - (a.despues.score - a.antes.score))
                .slice(0, 20)
                .map((c) => {
                  const delta = c.despues.score - c.antes.score;
                  return (
                    <div
                      key={c.id}
                      className="flex items-center justify-between gap-2 text-xs py-1 border-b hairline last:border-0"
                    >
                      <span className="text-ink truncate flex-1">{c.nombre}</span>
                      <span className="text-muted-foreground tabular shrink-0">
                        {c.antes.score} → {c.despues.score}
                      </span>
                      <span
                        className={`tabular shrink-0 inline-flex items-center gap-0.5 ${delta > 0 ? "text-verde-ink" : delta < 0 ? "text-destructive" : "text-muted-foreground"}`}
                      >
                        {delta > 0 ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : delta < 0 ? (
                          <TrendingDown className="h-3 w-3" />
                        ) : null}
                        {delta > 0 ? "+" : ""}
                        {delta}
                      </span>
                    </div>
                  );
                })}
              {reporte.cambios.length > 20 && (
                <div className="text-xs text-muted-foreground pt-1">
                  …y {reporte.cambios.length - 20} más.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
