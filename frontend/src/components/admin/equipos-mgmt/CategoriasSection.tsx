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
import { Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";

import { Button } from "@/design-system/ui/button";
import { Input } from "@/design-system/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/design-system/ui/dialog";

import { adminApi } from "@/lib/admin/api";
import { useConfirm } from "@/components/admin/useConfirm";
import { AddEquiposToCategoriaDialog } from "./AddEquiposToCategoriaDialog";
import { SpecTemplatesSection } from "@/components/admin/specs/SpecTemplatesSection";
import { NombreTemplateDialog } from "./NombreTemplateDialog";
import { type RowItem, type DragData, SortableRootItem } from "./CategoriasSectionHelpers";

export function CategoriasSection() {
  const qc = useQueryClient();
  const confirm = useConfirm();
  const listQ = useQuery({
    queryKey: ["admin", "categorias"],
    queryFn: () => adminApi.adminListCategorias(),
  });

  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [newChildFor, setNewChildFor] = useState<number | null>(null);
  const [newChildName, setNewChildName] = useState("");
  const [newRoot, setNewRoot] = useState("");
  const [hideEmpty, setHideEmpty] = useState(false);
  const [addingEquiposTo, setAddingEquiposTo] = useState<{ id: number; nombre: string } | null>(
    null,
  );
  const [editingSpecsFor, setEditingSpecsFor] = useState<{ id: number; nombre: string } | null>(
    null,
  );
  const [editingTemplateFor, setEditingTemplateFor] = useState<{
    id: number;
    nombre: string;
    template: string | null;
  } | null>(null);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "categorias"] });
    qc.invalidateQueries({ queryKey: ["categorias"] });
    qc.invalidateQueries({ queryKey: ["equipos"] });
  };

  const updateMut = useMutation({
    mutationFn: ({
      id,
      ...patch
    }: {
      id: number;
      nombre?: string;
      prioridad?: number;
      parent_id?: number | null;
      set_parent_null?: boolean;
    }) => adminApi.adminUpdateCategoria(id, patch),
    onSuccess: () => {
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const createMut = useMutation({
    mutationFn: (data: { nombre: string; prioridad?: number; parent_id?: number | null }) =>
      adminApi.adminCreateCategoria(data),
    onSuccess: () => {
      invalidate();
      toast.success("Categoría creada");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => adminApi.adminDeleteCategoria(id),
    onSuccess: () => {
      invalidate();
      toast.success("Categoría eliminada");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const reorderMut = useMutation({
    mutationFn: (ids: number[]) => adminApi.adminReorderCategorias(ids),
    onSuccess: () => {
      invalidate();
    },
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

  useEffect(() => {
    setLocalRoots(null);
    setLocalChildrenMap({});
  }, [tree.roots, tree.all]);

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
            onSuccess: () =>
              toast.success(
                `Movida a "${displayRoots.find((r) => r.id === targetParentId)?.nombre ?? "otra raíz"}"`,
              ),
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
            Árbol de hasta 3 niveles. Arrastrá para reordenar las raíces y subcategorías. Una
            subcategoría se puede mover a otra raíz arrastrándola al área de hijas correspondiente.
            Los nietos (3er nivel) se crean con el botón + en cada subcategoría.
          </p>
        </div>
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground select-none cursor-pointer shrink-0">
          {/* eslint-disable-next-line no-restricted-syntax -- checkbox nativo: el DS Checkbox es Radix (otra API) */}
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
          <SortableContext
            items={displayRoots.map((r) => r.id)}
            strategy={verticalListSortingStrategy}
          >
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
                    onDelete={async () => {
                      if (
                        await confirm({
                          title: `¿Eliminar "${root.nombre}"?`,
                          description: "Se desvincularán sus hijos.",
                          danger: true,
                          confirmLabel: "Eliminar",
                        })
                      ) {
                        deleteMut.mutate(root.id);
                      }
                    }}
                    onAddChild={() => {
                      setNewChildFor(root.id);
                      setNewChildName("");
                    }}
                    onAddEquipos={(id, nombre) => setAddingEquiposTo({ id, nombre })}
                    onEditSpecs={(id, nombre) => setEditingSpecsFor({ id, nombre })}
                    onEditTemplate={(id, nombre, template) =>
                      setEditingTemplateFor({ id, nombre, template })
                    }
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
                      updateMut.mutate(
                        pid === null ? { id, set_parent_null: true } : { id, parent_id: pid },
                      )
                    }
                    onDeleteChild={async (id, name) => {
                      if (
                        await confirm({
                          title: `¿Eliminar subcategoría "${name}"?`,
                          danger: true,
                          confirmLabel: "Eliminar",
                        })
                      )
                        deleteMut.mutate(id);
                    }}
                    grandchildrenOf={(childId) => childrenOfDisplay(childId)}
                    onCreateGrandchild={(parentId, name) =>
                      createMut.mutate({ nombre: name, parent_id: parentId })
                    }
                    onRenameGrandchild={(id, n) => updateMut.mutate({ id, nombre: n })}
                    onDeleteGrandchild={async (id, name) => {
                      if (
                        await confirm({
                          title: `¿Eliminar nieto "${name}"?`,
                          danger: true,
                          confirmLabel: "Eliminar",
                        })
                      )
                        deleteMut.mutate(id);
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
          onOpenChange={(v) => {
            if (!v) setAddingEquiposTo(null);
          }}
          categoriaId={addingEquiposTo.id}
          categoriaNombre={addingEquiposTo.nombre}
        />
      )}

      <Dialog
        open={!!editingSpecsFor}
        onOpenChange={(v) => {
          if (!v) setEditingSpecsFor(null);
        }}
      >
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Specs de "{editingSpecsFor?.nombre}"</DialogTitle>
          </DialogHeader>
          {editingSpecsFor && (
            <SpecTemplatesSection fixedCategoriaId={editingSpecsFor.id} showHeader={false} />
          )}
        </DialogContent>
      </Dialog>

      {editingTemplateFor && (
        <NombreTemplateDialog
          open={true}
          onOpenChange={(v) => {
            if (!v) setEditingTemplateFor(null);
          }}
          categoriaId={editingTemplateFor.id}
          categoriaNombre={editingTemplateFor.nombre}
          initialTemplate={editingTemplateFor.template}
        />
      )}
    </section>
  );
}
