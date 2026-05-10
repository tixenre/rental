/**
 * ClasificacionSection — clasificación automática de equipos por reglas.
 * Extraído de /admin/settings → /admin/equipos/clasificar.
 */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

import { adminApi, type ClasificarResult } from "@/lib/admin/api";

export function ClasificacionSection() {
  const qc = useQueryClient();
  const [preview, setPreview] = useState<ClasificarResult | null>(null);

  const dryRunMut = useMutation({
    mutationFn: () => adminApi.adminClasificarDryRun(),
    onSuccess: (r) => setPreview(r),
    onError: (e: Error) => toast.error(e.message),
  });

  const applyMut = useMutation({
    mutationFn: () => adminApi.adminClasificarApply(),
    onSuccess: (r) => {
      toast.success(`${r.applied} equipos clasificados`);
      setPreview(r);
      qc.invalidateQueries({ queryKey: ["categorias"] });
      qc.invalidateQueries({ queryKey: ["equipos"] });
      qc.invalidateQueries({ queryKey: ["admin", "etiquetas"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="font-display text-lg text-ink flex items-center gap-2">
            <Sparkles className="h-4 w-4" /> Clasificación automática de equipos
          </h2>
          <p className="text-sm text-muted-foreground">
            Aplica reglas por nombre/marca/modelo para asignar etiquetas hoja a cada equipo.
            Equipos como la a7 V se asignan a Foto y Video. Revisá el preview antes de aplicar
            — al aplicar, las etiquetas existentes de cada equipo con match se reemplazan.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" disabled={dryRunMut.isPending} onClick={() => dryRunMut.mutate()}>
          {dryRunMut.isPending && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
          Generar preview
        </Button>
        {preview && (
          <Button
            size="sm"
            disabled={applyMut.isPending || preview.matched === 0}
            onClick={() => {
              if (confirm(`Aplicar clasificación a ${preview.matched} equipos? Las etiquetas existentes serán reemplazadas.`)) {
                applyMut.mutate();
              }
            }}
          >
            {applyMut.isPending && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
            Aplicar a {preview.matched} equipos
          </Button>
        )}
      </div>

      {preview && (
        <div className="space-y-2">
          <div className="text-xs text-muted-foreground">
            Total: {preview.total} · con match: <strong className="text-ink">{preview.matched}</strong> ·
            sin match: <strong className="text-ink">{preview.unmatched}</strong>
            {preview.applied > 0 && <> · aplicados: <strong className="text-ink">{preview.applied}</strong></>}
          </div>
          <div className="max-h-80 overflow-auto border hairline rounded-md text-xs">
            <table className="w-full">
              <thead className="bg-muted/50 sticky top-0">
                <tr className="text-left">
                  <th className="px-2 py-1.5 font-medium">Equipo</th>
                  <th className="px-2 py-1.5 font-medium">Actuales</th>
                  <th className="px-2 py-1.5 font-medium">Propuestas</th>
                </tr>
              </thead>
              <tbody>
                {preview.items.map((it) => (
                  <tr key={it.id} className="border-t hairline">
                    <td className="px-2 py-1.5">
                      <div className="text-ink">{it.nombre}</div>
                      {it.marca && <div className="text-muted-foreground text-[10px]">{it.marca}</div>}
                    </td>
                    <td className="px-2 py-1.5 text-muted-foreground">
                      {it.actuales.length === 0 ? "—" : it.actuales.join(", ")}
                    </td>
                    <td className="px-2 py-1.5">
                      {it.propuestas.length === 0 ? (
                        <span className="text-destructive/80">sin match</span>
                      ) : (
                        <span className="text-ink">{it.propuestas.join(" + ")}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
