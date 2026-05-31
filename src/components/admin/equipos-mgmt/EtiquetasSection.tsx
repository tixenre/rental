/**
 * EtiquetasSection — gestión de la bolsa libre de keywords/etiquetas de equipos.
 * Extraído de /admin/settings → /admin/equipos/etiquetas.
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { adminApi } from "@/lib/admin/api";

export function EtiquetasSection() {
  const qc = useQueryClient();
  const listQ = useQuery({
    queryKey: ["admin", "etiquetas"],
    queryFn: () => adminApi.adminListEtiquetas(),
  });
  const [nueva, setNueva] = useState("");
  const [filter, setFilter] = useState("");

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "etiquetas"] });
    qc.invalidateQueries({ queryKey: ["etiquetas"] });
    qc.invalidateQueries({ queryKey: ["equipos"] });
  };

  const createMut = useMutation({
    mutationFn: (nombre: string) => adminApi.adminCreateEtiqueta({ nombre }),
    onSuccess: () => {
      invalidate();
      setNueva("");
      toast.success("Etiqueta creada");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const renameMut = useMutation({
    mutationFn: ({ id, nombre }: { id: number; nombre: string }) =>
      adminApi.adminUpdateEtiqueta(id, { nombre }),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => adminApi.adminDeleteEtiqueta(id),
    onSuccess: () => {
      invalidate();
      toast.success("Etiqueta eliminada");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const items = useMemo(() => {
    const all = listQ.data ?? [];
    const f = filter.trim().toLowerCase();
    const list = f ? all.filter((e) => e.nombre.toLowerCase().includes(f)) : all;
    return list.sort((a, b) => b.total - a.total || a.nombre.localeCompare(b.nombre));
  }, [listQ.data, filter]);

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Etiquetas libres</h2>
        <p className="text-sm text-muted-foreground">
          Bolsa de keywords para búsqueda. Marca, modelo, nombre y categorías se agregan
          automáticamente — usá esto para palabras adicionales (ej: "f/2.8", "4k60", "fullframe",
          "bicolor").
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Nueva etiqueta…"
          value={nueva}
          onChange={(e) => setNueva(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && nueva.trim()) createMut.mutate(nueva.trim());
          }}
          className="h-8 max-w-xs"
        />
        <Button
          size="sm"
          disabled={!nueva.trim() || createMut.isPending}
          onClick={() => createMut.mutate(nueva.trim())}
        >
          <Plus className="h-4 w-4 mr-1" /> Agregar
        </Button>
        <div className="flex-1" />
        <Input
          placeholder="Filtrar…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="h-8 max-w-xs"
        />
      </div>

      {listQ.isLoading && (
        <div className="py-6 text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Cargando…
        </div>
      )}
      {listQ.error && (
        <div className="text-sm text-destructive">Error: {(listQ.error as Error).message}</div>
      )}

      {items.length > 0 && (
        <ul className="divide-y hairline border hairline rounded-md max-h-96 overflow-auto">
          {items.map((et) => (
            <li key={et.id} className="flex items-center gap-2 px-3 py-1.5">
              <Input
                defaultValue={et.nombre}
                key={`${et.id}-${et.nombre}`}
                className="h-8 flex-1"
                onBlur={(e) => {
                  const v = e.target.value.trim();
                  if (v && v !== et.nombre) renameMut.mutate({ id: et.id, nombre: v });
                }}
              />
              <span className="text-[11px] text-muted-foreground tabular-nums w-10 text-right">
                {et.total}
              </span>
              <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8 text-destructive"
                onClick={() => {
                  if (confirm(`Eliminar etiqueta "${et.nombre}"?`)) deleteMut.mutate(et.id);
                }}
                title="Eliminar"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
