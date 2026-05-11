/**
 * CategoriasSection — gestión del árbol de categorías con drag-and-drop.
 *
 * - Raíces y sub-categorías se reordenan arrastrando (GripVertical).
 * - Reorder llama a POST /admin/categorias/reorder (asigna prioridad × 10).
 * - El input de prioridad manual desaparece.
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2, ChevronRight, ChevronDown, GripVertical } from "lucide-react";
import { toast } from "sonner";
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

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

  const reorderMut = useMutation({
    mutationFn: (ids: number[]) => adminApi.adminReorderCategorias(ids),
    onSuccess: invalidate,
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

  // Local state for optimistic reorder (roots)
  const [localRoots, setLocalRoots] = useState<RowItem[] | null>(null);
  const displayRoots = localRoots ?? tree.roots;

  // Sync local roots when server data changes
  useMemo(() => { setLocalRoots(null); }, [tree.roots]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleRootDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = displayRoots.findIndex((r) => r.id === active.id);
    const newIndex = displayRoots.findIndex((r) => r.id === over.id);
    const reordered = arrayMove(displayRoots, oldIndex, newIndex);
    setLocalRoots(reordered);
    reorderMut.mutate(reordered.map((r) => r.id));
  };

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Categorías</h2>
        <p className="text-sm text-muted-foreground">
          Árbol de 2 niveles. Arrastrá para reordenar. Las subcategorías heredan al padre.
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

      {displayRoots.length > 0 && (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleRootDragEnd}>
          <SortableContext items={displayRoots.map((r) => r.id)} strategy={verticalListSortingStrategy}>
            <ul className="divide-y hairline border hairline rounded-md">
              {displayRoots.map((root) => {
                const children = tree.childrenOf(root.id);
                const isOpen = expanded[root.id] ?? true;
                return (
                  <SortableRootItem
                    key={root.id}
                    root={root}
                    children={children}
                    allRoots={displayRoots}
                    isOpen={isOpen}
                    sensors={sensors}
                    onToggle={() => setExpanded((s) => ({ ...s, [root.id]: !isOpen }))}
                    onRename={(n) => updateMut.mutate({ id: root.id, nombre: n })}
                    onDelete={() => {
                      if (confirm(`Eliminar "${root.nombre}" y desvincular sus hijos?`)) {
                        deleteMut.mutate(root.id);
                      }
                    }}
                    onAddChild={() => { setNewChildFor(root.id); setNewChildName(""); }}
                    newChildFor={newChildFor}
                    newChildName={newChildName}
                    setNewChildName={setNewChildName}
                    onCreateChild={(name) => {
                      createMut.mutate({ nombre: name, parent_id: root.id });
                      setNewChildFor(null);
                    }}
                    onCancelChild={() => setNewChildFor(null)}
                    onReorderChildren={(ids) => reorderMut.mutate(ids)}
                    onRenameChild={(id, n) => updateMut.mutate({ id, nombre: n })}
                    onChangeParent={(id, pid) =>
                      updateMut.mutate(pid === null ? { id, set_parent_null: true } : { id, parent_id: pid })
                    }
                    onDeleteChild={(id, name) => {
                      if (confirm(`Eliminar subcategoría "${name}"?`)) deleteMut.mutate(id);
                    }}
                  />
                );
              })}
            </ul>
          </SortableContext>
        </DndContext>
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

// ── Sortable root item (con su propio DndContext para los hijos) ─────────────

function SortableRootItem({
  root, children, allRoots, isOpen, sensors,
  onToggle, onRename, onDelete, onAddChild,
  newChildFor, newChildName, setNewChildName,
  onCreateChild, onCancelChild,
  onReorderChildren, onRenameChild, onChangeParent, onDeleteChild,
}: {
  root: RowItem;
  children: RowItem[];
  allRoots: RowItem[];
  isOpen: boolean;
  sensors: ReturnType<typeof useSensors>;
  onToggle: () => void;
  onRename: (n: string) => void;
  onDelete: () => void;
  onAddChild: () => void;
  newChildFor: number | null;
  newChildName: string;
  setNewChildName: (v: string) => void;
  onCreateChild: (name: string) => void;
  onCancelChild: () => void;
  onReorderChildren: (ids: number[]) => void;
  onRenameChild: (id: number, name: string) => void;
  onChangeParent: (id: number, parentId: number | null) => void;
  onDeleteChild: (id: number, name: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: root.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 10 : undefined,
  };

  // Local state for children optimistic reorder
  const [localChildren, setLocalChildren] = useState<RowItem[] | null>(null);
  const displayChildren = localChildren ?? children;
  useMemo(() => { setLocalChildren(null); }, [children]);

  const handleChildDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = displayChildren.findIndex((c) => c.id === active.id);
    const newIndex = displayChildren.findIndex((c) => c.id === over.id);
    const reordered = arrayMove(displayChildren, oldIndex, newIndex);
    setLocalChildren(reordered);
    onReorderChildren(reordered.map((c) => c.id));
  };

  return (
    <li ref={setNodeRef} style={style} className="py-1">
      <div className="flex items-center gap-1.5 px-3 py-1.5">
        {/* Drag handle */}
        <button
          type="button"
          {...attributes}
          {...listeners}
          className="h-6 w-6 grid place-items-center text-muted-foreground/40 hover:text-muted-foreground cursor-grab active:cursor-grabbing touch-none"
          aria-label="Arrastrar"
        >
          <GripVertical className="h-4 w-4" />
        </button>

        {/* Expand/collapse */}
        <button
          type="button"
          onClick={onToggle}
          className="h-6 w-6 grid place-items-center text-muted-foreground"
          aria-label={isOpen ? "Colapsar" : "Expandir"}
        >
          {children.length > 0 ? (
            isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />
          ) : <span className="h-4 w-4 inline-block" />}
        </button>

        <Input
          defaultValue={root.nombre}
          key={`${root.id}-name-${root.nombre}`}
          className="h-8 flex-1 font-medium"
          onBlur={(e) => {
            const v = e.target.value.trim();
            if (v && v !== root.nombre) onRename(v);
          }}
        />
        <span className="text-[11px] text-muted-foreground tabular-nums w-10 text-right">
          {root.total}
        </span>
        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={onAddChild} title="Agregar subcategoría">
          <Plus className="h-4 w-4" />
        </Button>
        <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={onDelete} title="Eliminar">
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {isOpen && (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleChildDragEnd}>
          <SortableContext items={displayChildren.map((c) => c.id)} strategy={verticalListSortingStrategy}>
            <ul className="pl-8">
              {displayChildren.map((child) => (
                <SortableChildItem
                  key={child.id}
                  child={child}
                  parents={allRoots.filter((r) => r.id !== child.id)}
                  onRename={(n) => onRenameChild(child.id, n)}
                  onChangeParent={(pid) => onChangeParent(child.id, pid)}
                  onDelete={() => onDeleteChild(child.id, child.nombre)}
                />
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
                      if (e.key === "Enter" && newChildName.trim()) onCreateChild(newChildName.trim());
                      if (e.key === "Escape") onCancelChild();
                    }}
                  />
                  <Button size="sm" disabled={!newChildName.trim()} onClick={() => onCreateChild(newChildName.trim())}>
                    Agregar
                  </Button>
                  <Button size="sm" variant="ghost" onClick={onCancelChild}>Cancelar</Button>
                </li>
              )}
            </ul>
          </SortableContext>
        </DndContext>
      )}
    </li>
  );
}

function SortableChildItem({
  child, parents, onRename, onChangeParent, onDelete,
}: {
  child: RowItem;
  parents: RowItem[];
  onRename: (n: string) => void;
  onChangeParent: (parentId: number | null) => void;
  onDelete: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: child.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <li ref={setNodeRef} style={style}>
      <div className="flex items-center gap-1.5 px-3 py-1.5">
        <button
          type="button"
          {...attributes}
          {...listeners}
          className="h-6 w-6 grid place-items-center text-muted-foreground/40 hover:text-muted-foreground cursor-grab active:cursor-grabbing touch-none"
          aria-label="Arrastrar"
        >
          <GripVertical className="h-4 w-4" />
        </button>
        <Input
          defaultValue={child.nombre}
          key={`${child.id}-name-${child.nombre}`}
          className="h-8 flex-1"
          onBlur={(e) => {
            const v = e.target.value.trim();
            if (v && v !== child.nombre) onRename(v);
          }}
        />
        <span className="text-[11px] text-muted-foreground tabular-nums w-10 text-right">
          {child.total}
        </span>
        <Select
          value={child.parent_id ? String(child.parent_id) : "none"}
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
        <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={onDelete} title="Eliminar">
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </li>
  );
}
