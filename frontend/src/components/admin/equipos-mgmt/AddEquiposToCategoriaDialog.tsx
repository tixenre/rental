/**
 * AddEquiposToCategoriaDialog — modal para asignar masivamente equipos
 * a una categoría desde la vista de Categorías.
 *
 * Lista todos los equipos con search + multi-select. Los equipos que ya
 * pertenecen a la categoría aparecen pre-tildeados. Al guardar se llama
 * al bulk `add_categoria` (que no pisa otras categorías ya asignadas).
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { Spinner } from "@/design-system/ui/spinner";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/design-system/ui/dialog";
import { Checkbox } from "@/design-system/ui/checkbox";
import { adminApi } from "@/lib/admin/api";

export function AddEquiposToCategoriaDialog({
  open,
  onOpenChange,
  categoriaId,
  categoriaNombre,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  categoriaId: number;
  categoriaNombre: string;
}) {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const equiposQ = useQuery({
    queryKey: ["admin", "equipos-all-for-categoria"],
    queryFn: () => adminApi.listEquipos({ per_page: 500 }),
    enabled: open,
  });

  const items = useMemo(() => equiposQ.data?.items ?? [], [equiposQ.data?.items]);
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (e) =>
        e.nombre.toLowerCase().includes(q) ||
        (e.marca ?? "").toLowerCase().includes(q) ||
        (e.modelo ?? "").toLowerCase().includes(q),
    );
  }, [items, search]);

  // Equipos que YA están en la categoría — pre-tildeados y deshabilitados.
  const alreadyIn = useMemo(() => {
    const s = new Set<number>();
    for (const e of items) {
      if (e.categorias?.some((c) => c.id === categoriaId)) s.add(e.id);
    }
    return s;
  }, [items, categoriaId]);

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const addMut = useMutation({
    mutationFn: (ids: number[]) =>
      adminApi.bulkAction({ ids, action: "add_categoria", categoria_id: categoriaId }),
    onSuccess: (res) => {
      toast.success(`${res.affected} equipo(s) asignado(s) a "${categoriaNombre}"`);
      qc.invalidateQueries({ queryKey: ["admin", "categorias"] });
      qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
      qc.invalidateQueries({ queryKey: ["equipos"] });
      setSelected(new Set());
      onOpenChange(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const handleSave = () => {
    const ids = [...selected].filter((id) => !alreadyIn.has(id));
    if (ids.length === 0) {
      toast.info("No hay equipos nuevos para asignar");
      return;
    }
    addMut.mutate(ids);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Asignar equipos a "{categoriaNombre}"</DialogTitle>
          <DialogDescription>
            Tildá los equipos que querés agregar a esta categoría. Los que ya pertenecen aparecen
            marcados y bloqueados — esto NO reemplaza otras categorías que cada equipo ya tenga.
          </DialogDescription>
        </DialogHeader>

        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nombre, marca o modelo…"
            className="pl-9"
          />
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto rounded-md border hairline">
          {equiposQ.isLoading ? (
            <div className="flex items-center justify-center py-10 text-sm text-muted-foreground">
              <Spinner size="sm" className="mr-2" /> Cargando equipos…
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              {search ? "Sin resultados" : "No hay equipos cargados"}
            </div>
          ) : (
            <ul className="divide-y divide-muted/40">
              {filtered.map((e) => {
                const isIn = alreadyIn.has(e.id);
                const isPicked = selected.has(e.id);
                return (
                  <li
                    key={e.id}
                    className={`flex items-center gap-3 px-3 py-2 ${
                      isIn ? "opacity-60" : "hover:bg-muted/20 cursor-pointer"
                    }`}
                    onClick={() => !isIn && toggle(e.id)}
                  >
                    <Checkbox
                      checked={isIn || isPicked}
                      disabled={isIn}
                      onCheckedChange={() => !isIn && toggle(e.id)}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm text-ink">{e.nombre}</div>
                      <div className="text-2xs text-muted-foreground">
                        {[e.marca, e.modelo].filter(Boolean).join(" · ") || "—"}
                        {isIn && (
                          <span className="ml-2 text-ink/70">· ya está en esta categoría</span>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <DialogFooter>
          <div className="mr-auto text-xs text-muted-foreground self-center">
            {selected.size > 0 ? `${selected.size} seleccionado(s)` : "Tildá equipos para asignar"}
          </div>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button onClick={handleSave} disabled={selected.size === 0 || addMut.isPending}>
            {addMut.isPending ? "Guardando…" : "Asignar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
