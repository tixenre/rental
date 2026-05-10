/**
 * CategoriasSection — gestión del árbol de categorías de equipos (2 niveles).
 *
 * Extraído de /admin/settings para vivir bajo /admin/equipos/categorias en el
 * sidebar de admin. Se sigue usando como sección embebible si hace falta.
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2, ChevronRight, ChevronDown } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

import { adminApi } from "@/lib/admin/api";

type RowItem = { id: number; nombre: string; prioridad: number; parent_id: number | null; total: number };

export function CategoriasSection() {
  const qc = useQueryClient();
  const listQ = useQuery({
    queryKey: ["admin", "categorias"],
    queryFn: () => adminApi.adminListCategorias(),
  });

  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [newChildFor, setNewChildFor] = useState<number | null>(null);
  const [newChildName, setNewChildName] = useState("");
  const [newRoot, setNewRoot] = useState("");

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "categorias"] });
    qc.invalidateQueries({ queryKey: ["categorias"] });
    qc.invalidateQueries({ queryKey: ["equipos"] });
  };

  const updateMut = useMutation({
    mutationFn: ({ id, ...patch }: { id: number; nombre?: string; prioridad?: number; parent_id?: number | null; set_parent_null?: boolean }) =>
      adminApi.adminUpdateCategoria(id, patch),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });

  const createMut = useMutation({
    mutationFn: (data: { nombre: string; prioridad?: number; parent_id?: number | null }) =>
      adminApi.adminCreateCategoria(data),
    onSuccess: () => { invalidate(); toast.success("Categoría creada"); },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => adminApi.adminDeleteCategoria(id),
    onSuccess: () => { invalidate(); toast.success("Categoría eliminada"); },
    onError: (e: Error) => toast.error(e.message),
  });

  const tree = useMemo(() => {
    const all = listQ.data ?? [];
    const roots = all
      .filter((e) => e.parent_id == null)
      .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
    const childrenOf = (pid: number) =>
      all
        .filter((e) => e.parent_id === pid)
        .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
    return { roots, childrenOf, all };
  }, [listQ.data]);

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Categorías</h2>
        <p className="text-sm text-muted-foreground">
          Árbol de 2 niveles. Las subcategorías heredan al padre: filtrar por
          "Cámaras" muestra equipos de Foto, Video y Acción. Menor prioridad = más arriba.
        </p>
      </div>

      {listQ.isLoading && (
        <div className="py-6 text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Cargando…
        </div>
      )}
      {listQ.error && (
        <div className="text-sm text-destructive">Error: {(listQ.error as Error).message}</div>
      )}

      {tree.roots.length > 0 && (
        <ul className="divide-y hairline border hairline rounded-md">
          {tree.roots.map((root) => {
            const children = tree.childrenOf(root.id);
            const isOpen = expanded[root.id] ?? true;
            return (
              <li key={root.id} className="py-1">
                <CategoryRow
                  et={root}
                  isRoot
                  isOpen={isOpen}
                  hasChildren={children.length > 0}
                  onToggle={() => setExpanded((s) => ({ ...s, [root.id]: !isOpen }))}
                  onPriority={(v) => updateMut.mutate({ id: root.id, prioridad: v })}
                  onRename={(n) => updateMut.mutate({ id: root.id, nombre: n })}
                  onDelete={() => {
                    if (confirm(`Eliminar "${root.nombre}" y desvincular sus hijos?`)) {
                      deleteMut.mutate(root.id);
                    }
                  }}
                  onAddChild={() => { setNewChildFor(root.id); setNewChildName(""); }}
                />
                {isOpen && (
                  <ul className="pl-6">
                    {children.map((child) => (
                      <li key={child.id}>
                        <CategoryRow
                          et={child}
                          parents={tree.roots.filter((r) => r.id !== child.id)}
                          onPriority={(v) => updateMut.mutate({ id: child.id, prioridad: v })}
                          onRename={(n) => updateMut.mutate({ id: child.id, nombre: n })}
                          onChangeParent={(pid) =>
                            updateMut.mutate(
                              pid === null
                                ? { id: child.id, set_parent_null: true }
                                : { id: child.id, parent_id: pid },
                            )
                          }
                          onDelete={() => {
                            if (confirm(`Eliminar subcategoría "${child.nombre}"?`)) {
                              deleteMut.mutate(child.id);
                            }
                          }}
                        />
                      </li>
                    ))}
                    {newChildFor === root.id && (
                      <li className="px-3 py-2 flex items-center gap-2">
                        <Input
                          autoFocus
                          placeholder="Nombre de la subcategoría"
                          value={newChildName}
                          onChange={(e) => setNewChildName(e.target.value)}
                          className="h-8 flex-1"
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && newChildName.trim()) {
                              createMut.mutate({ nombre: newChildName.trim(), parent_id: root.id });
                              setNewChildFor(null);
                            }
                            if (e.key === "Escape") setNewChildFor(null);
                          }}
                        />
                        <Button
                          size="sm"
                          disabled={!newChildName.trim() || createMut.isPending}
                          onClick={() => {
                            createMut.mutate({ nombre: newChildName.trim(), parent_id: root.id });
                            setNewChildFor(null);
                          }}
                        >
                          Agregar
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setNewChildFor(null)}>
                          Cancelar
                        </Button>
                      </li>
                    )}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <div className="flex items-center gap-2 pt-2">
        <Input
          placeholder="Nueva categoría raíz"
          value={newRoot}
          onChange={(e) => setNewRoot(e.target.value)}
          className="h-8 max-w-xs"
          onKeyDown={(e) => {
            if (e.key === "Enter" && newRoot.trim()) {
              createMut.mutate({ nombre: newRoot.trim(), parent_id: null });
              setNewRoot("");
            }
          }}
        />
        <Button
          size="sm"
          disabled={!newRoot.trim() || createMut.isPending}
          onClick={() => {
            createMut.mutate({ nombre: newRoot.trim(), parent_id: null });
            setNewRoot("");
          }}
        >
          <Plus className="h-4 w-4 mr-1" /> Agregar raíz
        </Button>
      </div>
    </section>
  );
}

function CategoryRow({
  et, isRoot, isOpen, hasChildren, parents, onToggle, onPriority,
  onRename, onChangeParent, onDelete, onAddChild,
}: {
  et: RowItem;
  isRoot?: boolean;
  isOpen?: boolean;
  hasChildren?: boolean;
  parents?: RowItem[];
  onToggle?: () => void;
  onPriority: (v: number) => void;
  onRename: (n: string) => void;
  onChangeParent?: (parentId: number | null) => void;
  onDelete: () => void;
  onAddChild?: () => void;
}) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5">
      {isRoot ? (
        <button
          type="button"
          onClick={onToggle}
          className="h-6 w-6 grid place-items-center text-muted-foreground"
          aria-label={isOpen ? "Colapsar" : "Expandir"}
        >
          {hasChildren ? (
            isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />
          ) : <span className="h-4 w-4 inline-block" />}
        </button>
      ) : (
        <span className="h-6 w-6 inline-block" />
      )}
      <Input
        defaultValue={et.nombre}
        key={`${et.id}-name-${et.nombre}`}
        className={`h-8 flex-1 ${isRoot ? "font-medium" : ""}`}
        onBlur={(e) => {
          const v = e.target.value.trim();
          if (v && v !== et.nombre) onRename(v);
        }}
      />
      <span className="text-[11px] text-muted-foreground tabular-nums w-10 text-right">
        {et.total}
      </span>
      {!isRoot && parents && onChangeParent && (
        <Select
          value={et.parent_id ? String(et.parent_id) : "none"}
          onValueChange={(v) => onChangeParent(v === "none" ? null : Number(v))}
        >
          <SelectTrigger className="h-8 w-32 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="none">Sin padre</SelectItem>
            {parents.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>{p.nombre}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
      <Input
        type="number"
        defaultValue={et.prioridad}
        key={`${et.id}-pri-${et.prioridad}`}
        className="h-8 w-16 text-right tabular-nums"
        onBlur={(e) => {
          const v = parseInt(e.target.value);
          if (!Number.isNaN(v) && v !== et.prioridad) onPriority(v);
        }}
      />
      {isRoot && onAddChild && (
        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={onAddChild} title="Agregar subcategoría">
          <Plus className="h-4 w-4" />
        </Button>
      )}
      <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={onDelete} title="Eliminar">
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}
