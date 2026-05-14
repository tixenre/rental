/**
 * CategoriasSection — gestión del árbol de categorías con drag-and-drop.
 *
 * Drag-and-drop:
 * - Raíces: reorder con drag (mismo padre).
 * - Subcategorías: reorder dentro del mismo padre, O **moverse a otro padre**
 *   arrastrando hacia el área de hijas de otro root (#283).
 *
 * Implementación: un único `DndContext` top-level. Cada root tiene un
 * `useDroppable` zone que detecta cuando una hija de otro padre se suelta
 * encima — en ese caso se llama `adminUpdateCategoria` con el nuevo parent_id.
 */

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2, ChevronRight, ChevronDown, GripVertical, Check, X } from "lucide-react";
import { toast } from "sonner";
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors,
  useDroppable,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

import { adminApi } from "@/lib/admin/api";
import { AddEquiposToCategoriaDialog } from "./AddEquiposToCategoriaDialog";
import { EquiposCountToggle, EquiposPanel } from "./EquiposEnCategoriaList";
import { Users } from "lucide-react";

type RowItem = { id: number; nombre: string; prioridad: number; parent_id: number | null; total: number };

/** Tipos de elemento draggable. Va en `data` del useSortable / useDroppable. */
type DragData =
  | { type: "root"; rootId: number }
  | { type: "child"; childId: number; parentId: number }
  | { type: "root-zone"; rootId: number }
  | { type: "grandchild"; grandchildId: number; parentChildId: number }
  | { type: "child-zone"; childId: number };

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
  const [hideEmpty, setHideEmpty] = useState(false);
  const [addingEquiposTo, setAddingEquiposTo] = useState<{ id: number; nombre: string } | null>(null);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "categorias"] });
    qc.invalidateQueries({ queryKey: ["categorias"] });
    qc.invalidateQueries({ queryKey: ["equipos"] });
  };

  const updateMut = useMutation({
    mutationFn: ({ id, ...patch }: { id: number; nombre?: string; prioridad?: number; parent_id?: number | null; set_parent_null?: boolean }) =>
      adminApi.adminUpdateCategoria(id, patch),
    onSuccess: () => { invalidate(); },
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
    onSuccess: () => { invalidate(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const tree = useMemo(() => {
    const all = listQ.data ?? [];
    let roots = all
      .filter((e) => e.parent_id == null)
      .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
    const childrenOfAll = (pid: number) =>
      all
        .filter((e) => e.parent_id === pid)
        .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));

    let childrenOf = childrenOfAll;
    if (hideEmpty) {
      childrenOf = (pid: number) => childrenOfAll(pid).filter((c) => c.total > 0);
      roots = roots.filter((r) => r.total > 0 || childrenOfAll(r.id).some((c) => c.total > 0));
    }

    return { roots, childrenOf, all };
  }, [listQ.data, hideEmpty]);

  // Local state para drag optimistic. Mantiene una versión completa del árbol
  // que se actualiza al arrastrar. Se reinicia a null cuando llega nueva data
  // del server (que ya incluye los cambios).
  const [localRoots, setLocalRoots] = useState<RowItem[] | null>(null);
  const [localChildrenMap, setLocalChildrenMap] = useState<Record<number, RowItem[]>>({});
  const displayRoots = localRoots ?? tree.roots;
  const childrenOfDisplay = (pid: number): RowItem[] =>
    localChildrenMap[pid] ?? tree.childrenOf(pid);

  useEffect(() => { setLocalRoots(null); setLocalChildrenMap({}); }, [tree.roots, tree.all]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over) return;
    const activeData = active.data.current as DragData | undefined;
    const overData = over.data.current as DragData | undefined;
    if (!activeData) return;

    // ── Reorder de raíces o nest de root bajo otra ───────────────────
    if (activeData.type === "root") {
      // Si se suelta sobre una root-zone (área de hijas) de otra raíz,
      // mover este root para que sea hijo (nivel 2) de esa raíz.
      if (overData?.type === "root-zone" && overData.rootId !== activeData.rootId) {
        updateMut.mutate(
          { id: activeData.rootId, parent_id: overData.rootId },
          { onSuccess: () => toast.success("Movida bajo otra categoría") },
        );
        return;
      }
      // Si se suelta sobre una child-zone (área de nietos de un child),
      // mover este root para que sea nieto (nivel 3) de ese child.
      if (overData?.type === "child-zone") {
        updateMut.mutate(
          { id: activeData.rootId, parent_id: overData.childId },
          { onSuccess: () => toast.success("Movida como sub-subcategoría") },
        );
        return;
      }
      // Default: reorder entre roots.
      if (active.id === over.id) return;
      const oldIndex = displayRoots.findIndex((r) => r.id === activeData.rootId);
      const newIndex = displayRoots.findIndex((r) => r.id === Number(over.id));
      if (oldIndex < 0 || newIndex < 0) return;
      const reordered = arrayMove(displayRoots, oldIndex, newIndex);
      setLocalRoots(reordered);
      reorderMut.mutate(reordered.map((r) => r.id));
      return;
    }

    // ── Movimiento de hija ────────────────────────────────────────────
    if (activeData.type === "child") {
      const activeChildId = activeData.childId;
      const activeParentId = activeData.parentId;

      // Determinar el target parent:
      // - over es otra hija → mismo padre que esa hija
      // - over es una root-zone (área de hijas de un root) → ese root
      // - over es un root (header) → ese root
      let targetParentId: number | null = null;
      if (overData?.type === "child") {
        targetParentId = overData.parentId;
      } else if (overData?.type === "root-zone") {
        targetParentId = overData.rootId;
      } else if (overData?.type === "root") {
        targetParentId = overData.rootId;
      } else {
        return;
      }

      if (activeParentId === targetParentId) {
        // ── Reorder dentro del mismo padre ────────────────────────────
        if (active.id === over.id) return;
        const siblings = childrenOfDisplay(activeParentId);
        const oldIndex = siblings.findIndex((c) => c.id === activeChildId);
        const newIndex = siblings.findIndex((c) => c.id === Number(over.id));
        if (oldIndex < 0 || newIndex < 0) return;
        const reordered = arrayMove(siblings, oldIndex, newIndex);
        setLocalChildrenMap((m) => ({ ...m, [activeParentId]: reordered }));
        reorderMut.mutate(reordered.map((c) => c.id));
      } else {
        // ── Cross-parent: mover hija a otro padre (#283) ──────────────
        // Optimistic: sacar de la lista del padre actual, agregar al final
        // del nuevo padre.
        const oldSiblings = childrenOfDisplay(activeParentId);
        const newSiblings = childrenOfDisplay(targetParentId);
        const moved = oldSiblings.find((c) => c.id === activeChildId);
        if (!moved) return;
        const newOldSiblings = oldSiblings.filter((c) => c.id !== activeChildId);
        const newNewSiblings = [...newSiblings, { ...moved, parent_id: targetParentId }];
        setLocalChildrenMap((m) => ({
          ...m,
          [activeParentId]: newOldSiblings,
          [targetParentId]: newNewSiblings,
        }));
        updateMut.mutate(
          { id: activeChildId, parent_id: targetParentId },
          {
            onSuccess: () => toast.success(`Movida a "${displayRoots.find((r) => r.id === targetParentId)?.nombre ?? "otra raíz"}"`),
          },
        );
      }
    }

    // ── Movimiento de nieto (3er nivel) ───────────────────────────────
    if (activeData.type === "grandchild") {
      const activeGrandId = activeData.grandchildId;
      const activeParentId = activeData.parentChildId;

      // Target parent del nieto:
      //  - over es otro nieto → mismo padre que ese nieto
      //  - over es child-zone → el child padre de esa zona
      //  - over es el child header → ese child como nuevo padre
      let targetParentId: number | null = null;
      if (overData?.type === "grandchild") {
        targetParentId = overData.parentChildId;
      } else if (overData?.type === "child-zone") {
        targetParentId = overData.childId;
      } else if (overData?.type === "child") {
        targetParentId = overData.childId;
      } else {
        return;
      }

      if (activeParentId === targetParentId) {
        // Reorder de nietos dentro del mismo padre.
        if (active.id === over.id) return;
        const siblings = childrenOfDisplay(activeParentId);
        const oldIndex = siblings.findIndex((g) => g.id === activeGrandId);
        const newIndex = siblings.findIndex((g) => g.id === Number(over.id));
        if (oldIndex < 0 || newIndex < 0) return;
        const reordered = arrayMove(siblings, oldIndex, newIndex);
        setLocalChildrenMap((m) => ({ ...m, [activeParentId]: reordered }));
        reorderMut.mutate(reordered.map((g) => g.id));
      } else {
        // Cross-parent: mover nieto a otro child (también nivel 2).
        const oldSiblings = childrenOfDisplay(activeParentId);
        const newSiblings = childrenOfDisplay(targetParentId);
        const moved = oldSiblings.find((g) => g.id === activeGrandId);
        if (!moved) return;
        const newOldSiblings = oldSiblings.filter((g) => g.id !== activeGrandId);
        const newNewSiblings = [...newSiblings, { ...moved, parent_id: targetParentId }];
        setLocalChildrenMap((m) => ({
          ...m,
          [activeParentId]: newOldSiblings,
          [targetParentId]: newNewSiblings,
        }));
        updateMut.mutate({ id: activeGrandId, parent_id: targetParentId });
      }
    }
  };

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-lg text-ink">Categorías</h2>
          <p className="text-sm text-muted-foreground">
            Árbol de hasta 3 niveles. Arrastrá para reordenar las raíces y subcategorías. Una subcategoría se puede mover a otra raíz arrastrándola al área de hijas correspondiente. Los nietos (3er nivel) se crean con el botón + en cada subcategoría.
          </p>
        </div>
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground select-none cursor-pointer shrink-0">
          <input
            type="checkbox"
            checked={hideEmpty}
            onChange={(e) => setHideEmpty(e.target.checked)}
            className="h-3.5 w-3.5"
          />
          Ocultar vacías
        </label>
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
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={displayRoots.map((r) => r.id)} strategy={verticalListSortingStrategy}>
            <ul className="divide-y hairline border hairline rounded-md">
              {displayRoots.map((root) => {
                const children = childrenOfDisplay(root.id);
                const isOpen = expanded[root.id] ?? true;
                return (
                  <SortableRootItem
                    key={root.id}
                    root={root}
                    children={children}
                    allRoots={displayRoots}
                    isOpen={isOpen}
                    onToggle={() => setExpanded((s) => ({ ...s, [root.id]: !isOpen }))}
                    onRename={(n) => updateMut.mutate({ id: root.id, nombre: n })}
                    onDelete={() => {
                      if (confirm(`Eliminar "${root.nombre}" y desvincular sus hijos?`)) {
                        deleteMut.mutate(root.id);
                      }
                    }}
                    onAddChild={() => { setNewChildFor(root.id); setNewChildName(""); }}
                    onAddEquipos={(id, nombre) => setAddingEquiposTo({ id, nombre })}
                    newChildFor={newChildFor}
                    newChildName={newChildName}
                    setNewChildName={setNewChildName}
                    onCreateChild={(name) => {
                      createMut.mutate({ nombre: name, parent_id: root.id });
                      setNewChildFor(null);
                    }}
                    onCancelChild={() => setNewChildFor(null)}
                    onRenameChild={(id, n) => updateMut.mutate({ id, nombre: n })}
                    onChangeParent={(id, pid) =>
                      updateMut.mutate(pid === null ? { id, set_parent_null: true } : { id, parent_id: pid })
                    }
                    onDeleteChild={(id, name) => {
                      if (confirm(`Eliminar subcategoría "${name}"?`)) deleteMut.mutate(id);
                    }}
                    grandchildrenOf={(childId) => childrenOfDisplay(childId)}
                    onCreateGrandchild={(parentId, name) =>
                      createMut.mutate({ nombre: name, parent_id: parentId })
                    }
                    onRenameGrandchild={(id, n) => updateMut.mutate({ id, nombre: n })}
                    onDeleteGrandchild={(id, name) => {
                      if (confirm(`Eliminar nieto "${name}"?`)) deleteMut.mutate(id);
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

      {addingEquiposTo && (
        <AddEquiposToCategoriaDialog
          open={true}
          onOpenChange={(v) => { if (!v) setAddingEquiposTo(null); }}
          categoriaId={addingEquiposTo.id}
          categoriaNombre={addingEquiposTo.nombre}
        />
      )}
    </section>
  );
}

// ── Sortable root item ──────────────────────────────────────────────────────

function SortableRootItem({
  root, children, allRoots, isOpen,
  onToggle, onRename, onDelete, onAddChild,
  newChildFor, newChildName, setNewChildName,
  onCreateChild, onCancelChild,
  onRenameChild, onChangeParent, onDeleteChild,
  grandchildrenOf, onCreateGrandchild, onRenameGrandchild, onDeleteGrandchild,
  onAddEquipos,
}: {
  root: RowItem;
  children: RowItem[];
  allRoots: RowItem[];
  isOpen: boolean;
  onToggle: () => void;
  onRename: (n: string) => void;
  onDelete: () => void;
  onAddChild: () => void;
  newChildFor: number | null;
  newChildName: string;
  setNewChildName: (v: string) => void;
  onCreateChild: (name: string) => void;
  onCancelChild: () => void;
  onRenameChild: (id: number, name: string) => void;
  onChangeParent: (id: number, parentId: number | null) => void;
  onDeleteChild: (id: number, name: string) => void;
  grandchildrenOf: (childId: number) => RowItem[];
  onCreateGrandchild: (parentId: number, name: string) => void;
  onRenameGrandchild: (id: number, name: string) => void;
  onDeleteGrandchild: (id: number, name: string) => void;
  onAddEquipos: (id: number, nombre: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({
      id: root.id,
      data: { type: "root", rootId: root.id } satisfies DragData,
    });

  // Droppable zone para recibir hijas de otros padres (cross-parent move).
  const dropZone = useDroppable({
    id: `root-zone-${root.id}`,
    data: { type: "root-zone", rootId: root.id } satisfies DragData,
  });

  const [equiposOpen, setEquiposOpen] = useState(false);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 10 : undefined,
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

        <EditableNameInput
          value={root.nombre}
          onSave={onRename}
          className="h-8 flex-1 font-medium"
        />
        <EquiposCountToggle
          count={root.total}
          isOpen={equiposOpen}
          onToggle={() => setEquiposOpen((v) => !v)}
          onAddWhenEmpty={() => onAddEquipos(root.id, root.nombre)}
        />
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8 text-muted-foreground hover:text-ink"
          onClick={() => onAddEquipos(root.id, root.nombre)}
          title="Asignar equipos a esta categoría"
        >
          <Users className="h-4 w-4" />
        </Button>
        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={onAddChild} title="Agregar subcategoría">
          <Plus className="h-4 w-4" />
        </Button>
        <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={onDelete} title="Eliminar">
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {equiposOpen && (
        <EquiposPanel
          categoriaId={root.id}
          categoriaNombre={root.nombre}
          indentLevel={1}
          onAddEquipos={onAddEquipos}
        />
      )}

      {isOpen && (
        <div
          ref={dropZone.setNodeRef}
          className={cn(
            "pl-8 transition rounded-md",
            // Resalte cuando una hija de otro padre está sobre esta zone.
            dropZone.isOver && "ring-2 ring-amber bg-amber/5",
          )}
        >
          <SortableContext items={children.map((c) => c.id)} strategy={verticalListSortingStrategy}>
            <ul>
              {children.map((child) => (
                <SortableChildItem
                  key={child.id}
                  child={child}
                  parents={allRoots.filter((r) => r.id !== child.id)}
                  grandchildren={grandchildrenOf(child.id)}
                  onRename={(n) => onRenameChild(child.id, n)}
                  onChangeParent={(pid) => onChangeParent(child.id, pid)}
                  onDelete={() => onDeleteChild(child.id, child.nombre)}
                  onCreateGrandchild={onCreateGrandchild}
                  onRenameGrandchild={onRenameGrandchild}
                  onDeleteGrandchild={onDeleteGrandchild}
                  onAddEquipos={onAddEquipos}
                />
              ))}
              {children.length === 0 && (
                <li className="px-3 py-3 text-[11px] text-muted-foreground/60 italic">
                  Sin subcategorías. Arrastrá una de otra raíz acá, o creá nueva con el +.
                </li>
              )}
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
        </div>
      )}
    </li>
  );
}

function SortableChildItem({
  child, parents, grandchildren = [],
  onRename, onChangeParent, onDelete,
  onCreateGrandchild, onRenameGrandchild, onDeleteGrandchild,
  onAddEquipos,
}: {
  child: RowItem;
  parents: RowItem[];
  grandchildren?: RowItem[];
  onRename: (n: string) => void;
  onChangeParent: (parentId: number | null) => void;
  onDelete: () => void;
  onCreateGrandchild?: (parentId: number, name: string) => void;
  onRenameGrandchild?: (id: number, name: string) => void;
  onDeleteGrandchild?: (id: number, name: string) => void;
  onAddEquipos?: (id: number, nombre: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({
      id: child.id,
      data: { type: "child", childId: child.id, parentId: child.parent_id ?? 0 } satisfies DragData,
    });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const [addingGrand, setAddingGrand] = useState(false);
  const [newGrandName, setNewGrandName] = useState("");
  const [equiposOpen, setEquiposOpen] = useState(false);

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
        <EditableNameInput
          value={child.nombre}
          onSave={onRename}
          className="h-8 flex-1"
        />
        <EquiposCountToggle
          count={child.total}
          isOpen={equiposOpen}
          onToggle={() => setEquiposOpen((v) => !v)}
          onAddWhenEmpty={onAddEquipos ? () => onAddEquipos(child.id, child.nombre) : undefined}
        />
        {onAddEquipos && (
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground hover:text-ink"
            onClick={() => onAddEquipos(child.id, child.nombre)}
            title="Asignar equipos a esta subcategoría"
          >
            <Users className="h-4 w-4" />
          </Button>
        )}
        {onCreateGrandchild && (
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground hover:text-ink"
            onClick={() => { setAddingGrand(true); setNewGrandName(""); }}
            title="Agregar nieto"
          >
            <Plus className="h-4 w-4" />
          </Button>
        )}
        <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={onDelete} title="Eliminar">
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {equiposOpen && (
        <EquiposPanel
          categoriaId={child.id}
          categoriaNombre={child.nombre}
          indentLevel={2}
          onAddEquipos={onAddEquipos}
        />
      )}

      {/* Nietos (3er nivel) — drag-drop reorder + cross-parent.
       *  SortableContext anida bajo el DndContext top-level del componente.
       *  La zona droppable de cada child (`child-zone-{id}`) recibe nietos
       *  arrastrados desde otro child. */}
      {(grandchildren.length > 0 || addingGrand) && (
        <ChildZone childId={child.id}>
          <SortableContext
            items={grandchildren.map((g) => g.id)}
            strategy={verticalListSortingStrategy}
          >
            <ul className="ml-10 border-l hairline">
              {grandchildren.map((g) => (
                <SortableGrandchildItem
                  key={g.id}
                  grand={g}
                  parentChildId={child.id}
                  onRename={(n) => onRenameGrandchild?.(g.id, n)}
                  onDelete={() => onDeleteGrandchild?.(g.id, g.nombre)}
                  onAddEquipos={onAddEquipos}
                />
              ))}
              {addingGrand && (
            <li className="px-3 py-1.5 flex items-center gap-2">
              <Input
                autoFocus
                placeholder="Nombre del nieto (3er nivel)"
                value={newGrandName}
                onChange={(e) => setNewGrandName(e.target.value)}
                className="h-7 flex-1"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newGrandName.trim() && onCreateGrandchild) {
                    onCreateGrandchild(child.id, newGrandName.trim());
                    setAddingGrand(false);
                  }
                  if (e.key === "Escape") setAddingGrand(false);
                }}
              />
              <Button
                size="sm"
                disabled={!newGrandName.trim()}
                onClick={() => {
                  if (onCreateGrandchild && newGrandName.trim()) {
                    onCreateGrandchild(child.id, newGrandName.trim());
                    setAddingGrand(false);
                  }
                }}
              >
                Agregar
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setAddingGrand(false)}>
                Cancelar
              </Button>
            </li>
          )}
            </ul>
          </SortableContext>
        </ChildZone>
      )}
    </li>
  );
}

function ChildZone({ childId, children }: { childId: number; children: React.ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({
    id: `child-zone-${childId}`,
    data: { type: "child-zone", childId } satisfies DragData,
  });
  return (
    <div ref={setNodeRef} className={isOver ? "bg-amber-soft/30" : undefined}>
      {children}
    </div>
  );
}

function SortableGrandchildItem({
  grand, parentChildId, onRename, onDelete, onAddEquipos,
}: {
  grand: RowItem;
  parentChildId: number;
  onRename: (n: string) => void;
  onDelete: () => void;
  onAddEquipos?: (id: number, nombre: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({
      id: grand.id,
      data: { type: "grandchild", grandchildId: grand.id, parentChildId } satisfies DragData,
    });

  const [equiposOpen, setEquiposOpen] = useState(false);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <li ref={setNodeRef} style={style}>
      <div className="flex items-center gap-1.5 px-3 py-1">
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="h-5 w-5 grid place-items-center text-muted-foreground/40 hover:text-muted-foreground cursor-grab active:cursor-grabbing touch-none"
        aria-label="Arrastrar nieto"
      >
        <GripVertical className="h-3 w-3" />
      </button>
      <EditableNameInput
        value={grand.nombre}
        onSave={onRename}
        className="h-7 flex-1"
      />
      <EquiposCountToggle
        count={grand.total}
        isOpen={equiposOpen}
        onToggle={() => setEquiposOpen((v) => !v)}
        onAddWhenEmpty={onAddEquipos ? () => onAddEquipos(grand.id, grand.nombre) : undefined}
      />
      {onAddEquipos && (
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7 text-muted-foreground hover:text-ink"
          onClick={() => onAddEquipos(grand.id, grand.nombre)}
          title="Asignar equipos a esta categoría"
        >
          <Users className="h-3.5 w-3.5" />
        </Button>
      )}
      <Button
        size="icon"
        variant="ghost"
        className="h-7 w-7 text-destructive"
        onClick={onDelete}
        title="Eliminar"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
      </div>
      {equiposOpen && (
        <EquiposPanel
          categoriaId={grand.id}
          categoriaNombre={grand.nombre}
          indentLevel={3}
          onAddEquipos={onAddEquipos}
        />
      )}
    </li>
  );
}


// ── Input editable con feedback visual ────────────────────────────────────────
//
// El input anterior usaba `defaultValue + onBlur` → silencioso, sin
// indicador de "dirty" ni botón de save. El admin tipeaba, no veía nada y
// asumía "no se puede editar". Issue #94.
//
// Este componente:
// - Estado local controlado.
// - Cuando hay cambios sin guardar (dirty): aparece botón ✓ (guardar) y ✗ (cancelar).
// - Guarda al click del check o Enter; cancela con Escape o click en ✗.
// - Re-sincroniza con `value` si cambia desde afuera (re-fetch post-save).

function EditableNameInput({
  value,
  onSave,
  className,
}: {
  value: string;
  onSave: (v: string) => void;
  className?: string;
}) {
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  const trimmed = draft.trim();
  const dirty = trimmed !== value && trimmed.length > 0;

  const save = () => {
    if (dirty) onSave(trimmed);
  };
  const cancel = () => {
    setDraft(value);
  };

  return (
    <div className="flex items-center gap-1 flex-1">
      <Input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            save();
          }
          if (e.key === "Escape") {
            e.preventDefault();
            cancel();
          }
        }}
        className={className}
      />
      {dirty && (
        <>
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-green-600 hover:text-green-700 hover:bg-green-50 shrink-0"
            onClick={save}
            title="Guardar (Enter)"
          >
            <Check className="h-4 w-4" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground hover:bg-muted shrink-0"
            onClick={cancel}
            title="Cancelar (Esc)"
          >
            <X className="h-4 w-4" />
          </Button>
        </>
      )}
    </div>
  );
}
