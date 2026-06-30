import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { Spinner } from "@/design-system/ui/spinner";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";

import { AdminTable, type Column } from "@/components/admin/AdminTable";
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

  const columns: Column<(typeof sorted)[number]>[] = [
    {
      header: "Jornadas",
      className: "tabular-nums font-medium",
      cell: (p) => (
        <>
          {p.jornadas} {p.jornadas === 1 ? "día" : "días"}
        </>
      ),
    },
    {
      header: "Descuento",
      className: "tabular-nums text-verde-ink font-medium",
      cell: (p) => `${p.pct}%`,
    },
    {
      header: <span className="text-xs">Ej. interpol.</span>,
      className: "text-xs text-muted-foreground",
      cell: (p, i) => {
        const siguiente = sorted[i + 1];
        const medio = siguiente ? Math.round((p.jornadas + siguiente.jornadas) / 2) : null;
        const pctMedio = medio ? interpolarDescuento(sorted, medio) : null;
        return pctMedio !== null ? `${medio} días → ${pctMedio}%` : "—";
      },
    },
    {
      header: "",
      headClassName: "w-10",
      cell: (p) => (
        <button
          onClick={() => borrar.mutate(p.id)}
          className="text-muted-foreground hover:text-destructive"
          disabled={borrar.isPending}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      ),
    },
  ];

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
        <Spinner size="sm" className="text-muted-foreground" />
      ) : sorted.length === 0 ? (
        <p className="text-sm text-muted-foreground italic">
          Sin descuentos configurados. Todos los alquileres aplican 0%.
        </p>
      ) : (
        <AdminTable columns={columns} rows={sorted} getRowKey={(p) => p.id} />
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
          {crear.isPending ? <Spinner size="xs" /> : <Plus className="w-3.5 h-3.5" />}
          Agregar
        </Button>
      </div>
    </section>
  );
}
