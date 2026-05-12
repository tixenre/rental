/**
 * Specs editor con diff visual cuando hay propuestos del autocompletar.
 *
 * - Propuestos = vienen del autocompletar, esperan aprobación.
 * - Actuales = ya están guardados en la ficha, soportan drag-and-drop.
 *
 * El usuario puede aceptar uno por uno (reemplaza o agrega), descartar o editar.
 * Extraído del form principal para reducir su tamaño (#207).
 */

import { Plus, Trash2, GripVertical } from "lucide-react";
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

import { type Spec, newSpec, sameLabel } from "./spec-helpers";

export function SpecsDiffEditor({
  specs, propuestos, onChange, onAceptarPropuesto, onDescartarPropuesto,
}: {
  specs: Spec[];
  propuestos: Spec[];
  onChange: (s: Spec[]) => void;
  onAceptarPropuesto: (s: Spec) => void;
  onDescartarPropuesto: (s: Spec) => void;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const updateSpec = (id: string, patch: Partial<Spec>) => {
    onChange(specs.map((s) => s.id === id ? { ...s, ...patch } : s));
  };
  const removeSpec = (id: string) => onChange(specs.filter((s) => s.id !== id));
  const addSpec = () => onChange([...specs, newSpec()]);

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = specs.findIndex((s) => s.id === active.id);
    const newIdx = specs.findIndex((s) => s.id === over.id);
    if (oldIdx === -1 || newIdx === -1) return;
    onChange(arrayMove(specs, oldIdx, newIdx));
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {specs.length > 0 && (
            <>
              {specs.length} {specs.length === 1 ? "ítem" : "ítems"}
              {specs.length > 1 && (
                <span className="ml-1.5 opacity-60">· arrastrá para reordenar</span>
              )}
            </>
          )}
        </span>
        <Button type="button" size="sm" variant="ghost" onClick={addSpec}>
          <Plus className="h-3 w-3 mr-1" /> Agregar
        </Button>
      </div>

      {/* Propuestos (del autocompletar) */}
      {propuestos.length > 0 && (
        <div className="rounded-md border hairline bg-amber-soft/30 p-2 space-y-1.5">
          <p className="text-[11px] text-ink/70 font-medium">
            ✨ {propuestos.length} {propuestos.length === 1 ? "ítem propuesto" : "ítems propuestos"} del autocompletar
          </p>
          {propuestos.map((s) => {
            const existing = specs.find((x) => sameLabel(x.label, s.label));
            return (
              <div key={s.id} className="flex items-center gap-1.5 text-xs">
                <div className="flex-1 min-w-0">
                  <span className="font-medium">{s.label}:</span>{" "}
                  <span>{s.value}</span>
                  {existing && existing.value !== s.value && (
                    <span className="ml-1 text-muted-foreground line-through">{existing.value}</span>
                  )}
                </div>
                <Button type="button" size="sm" variant="default" className="h-6 px-1.5 text-[10px]"
                  onClick={() => onAceptarPropuesto(s)}>
                  ✓
                </Button>
                <Button type="button" size="sm" variant="outline" className="h-6 px-1.5 text-[10px]"
                  onClick={() => onDescartarPropuesto(s)}>
                  ✗
                </Button>
              </div>
            );
          })}
        </div>
      )}

      {/* Specs actuales con drag-and-drop */}
      {specs.length > 0 ? (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={specs.map((s) => s.id)} strategy={verticalListSortingStrategy}>
            <div className="space-y-1">
              {specs.map((s) => (
                <SortableSpec
                  key={s.id}
                  spec={s}
                  onUpdate={(patch) => updateSpec(s.id, patch)}
                  onRemove={() => removeSpec(s.id)}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      ) : (
        propuestos.length === 0 && (
          <p className="text-xs text-muted-foreground italic">Sin ítems.</p>
        )
      )}
    </div>
  );
}

function SortableSpec({
  spec, onUpdate, onRemove,
}: {
  spec: Spec;
  onUpdate: (patch: Partial<Spec>) => void;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: spec.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="flex gap-1 items-center bg-background">
      <button
        type="button"
        className="cursor-grab active:cursor-grabbing text-muted-foreground/40 hover:text-muted-foreground touch-none px-0.5"
        {...attributes}
        {...listeners}
        tabIndex={-1}
      >
        <GripVertical className="h-3.5 w-3.5" />
      </button>
      <Input
        value={spec.label}
        onChange={(e) => onUpdate({ label: e.target.value })}
        placeholder="Spec"
        className="text-xs"
      />
      <Input
        value={spec.value}
        onChange={(e) => onUpdate({ value: e.target.value })}
        placeholder="Valor"
        className="text-xs"
      />
      <Button type="button" size="icon" variant="ghost" onClick={onRemove}>
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}
