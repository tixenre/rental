import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";

import { descuentosJornadaApi } from "@/lib/admin/api";
import { interpolarDescuento } from "@/lib/api";

export function DescuentosJornadaSection() {
  const qc = useQueryClient();
  const [dias, setDias] = useState("");
  const [pct, setPct] = useState("");

  const { data: puntos = [], isLoading } = useQuery({
    queryKey: ["descuentos-jornada"],
    queryFn: descuentosJornadaApi.list,
    staleTime: 5 * 60 * 1000,
  });

  const crear = useMutation({
    mutationFn: () => descuentosJornadaApi.create({ jornadas: Number(dias), pct: Number(pct) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["descuentos-jornada"] });
      setDias("");
      setPct("");
    },
    onError: () => toast.error("Error al guardar"),
  });

  const borrar = useMutation({
    mutationFn: (id: number) => descuentosJornadaApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["descuentos-jornada"] }),
    onError: () => toast.error("Error al eliminar"),
  });

  const sorted = [...puntos].sort((a, b) => a.jornadas - b.jornadas);

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-4">
      <div>
        <h2 className="font-display text-lg text-ink">Descuentos por jornadas</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Definí puntos ancla. Los valores intermedios se interpolan automáticamente.
        </p>
      </div>

      {/* Tabla de puntos */}
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
      ) : sorted.length === 0 ? (
        <p className="text-sm text-muted-foreground italic">
          Sin descuentos configurados. Todos los alquileres aplican 0%.
        </p>
      ) : (
        <div className="border hairline rounded-md overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/40">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Jornadas</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Descuento</th>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground text-xs">
                  Ej. interpol.
                </th>
                <th className="px-3 py-2 w-10" />
              </tr>
            </thead>
            <tbody className="divide-y hairline">
              {sorted.map((p, i) => {
                const siguiente = sorted[i + 1];
                const medio = siguiente ? Math.round((p.jornadas + siguiente.jornadas) / 2) : null;
                const pctMedio = medio ? interpolarDescuento(sorted, medio) : null;
                return (
                  <tr key={p.id}>
                    <td className="px-3 py-2 tabular-nums font-medium">
                      {p.jornadas} {p.jornadas === 1 ? "día" : "días"}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-verde-ink font-medium">{p.pct}%</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {pctMedio !== null ? `${medio} días → ${pctMedio}%` : "—"}
                    </td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => borrar.mutate(p.id)}
                        className="text-muted-foreground hover:text-destructive"
                        disabled={borrar.isPending}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Agregar punto */}
      <div className="flex items-end gap-2">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Jornadas</label>
          <Input
            type="number"
            min="1"
            value={dias}
            onChange={(e) => setDias(e.target.value)}
            placeholder="7"
            className="w-24 h-8 text-sm"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Descuento %</label>
          <Input
            type="number"
            min="0"
            max="100"
            step="0.5"
            value={pct}
            onChange={(e) => setPct(e.target.value)}
            placeholder="10"
            className="w-24 h-8 text-sm"
          />
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => crear.mutate()}
          disabled={!dias || !pct || crear.isPending}
        >
          {crear.isPending ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Plus className="w-3.5 h-3.5" />
          )}
          Agregar
        </Button>
      </div>
    </section>
  );
}
