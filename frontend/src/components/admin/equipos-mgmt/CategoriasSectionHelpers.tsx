/**
 * CategoriasSectionHelpers — sub-componentes de CategoriasSection.
 *
 * Extraídos para mantener el módulo principal manejable.
 * Sin cambios de lógica (move-verbatim).
 */

import { useEffect, useState } from "react";
import {
  GripVertical,
  Plus,
  Trash2,
  Users,
  Wrench,
  Type,
  Check,
  X,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { cn } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EquiposCountToggle, EquiposPanel } from "./EquiposEnCategoriaList";

export type RowItem = {
  id: number;
  nombre: string;
  prioridad: number;
  parent_id: number | null;
  total: number;
  nombre_publico_template?: string | null;
};

/** Tipos de elemento draggable. Va en `data` del useSortable / useDroppable. */
export type DragData =
  | { type: "root"; rootId: number }
  | { type: "child"; childId: number; parentId: number }
  | { type: "root-zone"; rootId: number }
  | { type: "grandchild"; grandchildId: number; parentChildId: number }
  | { type: "child-zone"; childId: number };

// ── Sortable root item ──────────────────────────────────────────────────────

export function SortableRootItem({
  root,
  children,
  allRoots,
  isOpen,
  onToggle,
  onRename,
  onDelete,
  onAddChild,
  newChildFor,
  newChildName,
  setNewChildName,
  onCreateChild,
  onCancelChild,
  onRenameChild,
  onChangeParent,
  onDeleteChild,
  grandchildrenOf,
  onCreateGrandchild,
  onRenameGrandchild,
  onDeleteGrandchild,
  onAddEquipos,
  onEditSpecs,
  onEditTemplate,
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
  onEditSpecs: (id: number, nombre: string) => void;
  onEditTemplate: (id: number, nombre: string, template: string | null) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
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
            isOpen ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )
          ) : (
            <span className="h-4 w-4 inline-block" />
          )}
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
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8 text-muted-foreground hover:text-ink"
          onClick={() => onEditSpecs(root.id, root.nombre)}
          title="Editar specs de esta categoría"
        >
          <Wrench className="h-4 w-4" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8 text-muted-foreground hover:text-ink"
          onClick={() => onEditTemplate(root.id, root.nombre, root.nombre_publico_template ?? null)}
          title="Plantilla de nombre público"
        >
          <Type className="h-4 w-4" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8"
          onClick={onAddChild}
          title="Agregar subcategoría"
        >
          <Plus className="h-4 w-4" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8 text-destructive"
          onClick={onDelete}
          title="Eliminar"
        >
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
                  onEditSpecs={onEditSpecs}
                  onEditTemplate={onEditTemplate}
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
                      if (e.key === "Enter" && newChildName.trim())
                        onCreateChild(newChildName.trim());
                      if (e.key === "Escape") onCancelChild();
                    }}
                  />
                  <Button
                    size="sm"
                    disabled={!newChildName.trim()}
                    onClick={() => onCreateChild(newChildName.trim())}
                  >
                    Agregar
                  </Button>
                  <Button size="sm" variant="ghost" onClick={onCancelChild}>
                    Cancelar
                  </Button>
                </li>
              )}
            </ul>
          </SortableContext>
        </div>
      )}
    </li>
  );
}

export function SortableChildItem({
  child,
  parents,
  grandchildren = [],
  onRename,
  onChangeParent,
  onDelete,
  onCreateGrandchild,
  onRenameGrandchild,
  onDeleteGrandchild,
  onAddEquipos,
  onEditSpecs,
  onEditTemplate,
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
  onEditSpecs?: (id: number, nombre: string) => void;
  onEditTemplate?: (id: number, nombre: string, template: string | null) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
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
        <EditableNameInput value={child.nombre} onSave={onRename} className="h-8 flex-1" />
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
        {onEditSpecs && (
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground hover:text-ink"
            onClick={() => onEditSpecs(child.id, child.nombre)}
            title="Editar specs de esta subcategoría"
          >
            <Wrench className="h-4 w-4" />
          </Button>
        )}
        {onEditTemplate && (
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground hover:text-ink"
            onClick={() =>
              onEditTemplate(child.id, child.nombre, child.nombre_publico_template ?? null)
            }
            title="Plantilla de nombre público"
          >
            <Type className="h-4 w-4" />
          </Button>
        )}
        {onCreateGrandchild && (
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 text-muted-foreground hover:text-ink"
            onClick={() => {
              setAddingGrand(true);
              setNewGrandName("");
            }}
            title="Agregar nieto"
          >
            <Plus className="h-4 w-4" />
          </Button>
        )}
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8 text-destructive"
          onClick={onDelete}
          title="Eliminar"
        >
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
                  onEditSpecs={onEditSpecs}
                  onEditTemplate={onEditTemplate}
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

export function ChildZone({ childId, children }: { childId: number; children: React.ReactNode }) {
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

export function SortableGrandchildItem({
  grand,
  parentChildId,
  onRename,
  onDelete,
  onAddEquipos,
  onEditSpecs,
  onEditTemplate,
}: {
  grand: RowItem;
  parentChildId: number;
  onRename: (n: string) => void;
  onDelete: () => void;
  onAddEquipos?: (id: number, nombre: string) => void;
  onEditSpecs?: (id: number, nombre: string) => void;
  onEditTemplate?: (id: number, nombre: string, template: string | null) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
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
        <EditableNameInput value={grand.nombre} onSave={onRename} className="h-7 flex-1" />
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
        {onEditSpecs && (
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7 text-muted-foreground hover:text-ink"
            onClick={() => onEditSpecs(grand.id, grand.nombre)}
            title="Editar specs de esta categoría"
          >
            <Wrench className="h-3.5 w-3.5" />
          </Button>
        )}
        {onEditTemplate && (
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7 text-muted-foreground hover:text-ink"
            onClick={() =>
              onEditTemplate(grand.id, grand.nombre, grand.nombre_publico_template ?? null)
            }
            title="Plantilla de nombre público"
          >
            <Type className="h-3.5 w-3.5" />
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

export function EditableNameInput({
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
            className="h-8 w-8 text-verde hover:text-verde/80 hover:bg-verde/10 shrink-0"
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
