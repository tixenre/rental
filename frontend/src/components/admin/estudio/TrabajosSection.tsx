import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { Film, Plus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/design-system/ui/button";
import { EmptyState } from "@/design-system/composites/EmptyState";
import { trabajosAdminApi, type EstudioTrabajo } from "@/lib/admin/api";
import { Section } from "./shared";
import { SortableTrabajoCard } from "./SortableTrabajoCard";
import { TrabajoDialog, type TrabajoDialogMode } from "./TrabajoDialog";

export function TrabajosSection({
  trabajos: initialTrabajos,
  onChanged,
}: {
  trabajos: EstudioTrabajo[];
  onChanged: () => void;
}) {
  const [trabajos, setTrabajos] = useState(initialTrabajos);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<TrabajoDialogMode>({ mode: "create" });

  useEffect(() => {
    setTrabajos(initialTrabajos);
  }, [initialTrabajos]);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const deleteMut = useMutation({
    mutationFn: (id: number) => trabajosAdminApi.delete(id),
    onSuccess: () => {
      toast.success("Trabajo eliminado");
      onChanged();
    },
    onError: (e) => toast.error("Error eliminando", { description: (e as Error).message }),
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, activo }: { id: number; activo: boolean }) =>
      trabajosAdminApi.update(id, { activo }),
    onSuccess: (updated) => {
      setTrabajos((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    },
    onError: (e) => toast.error("Error", { description: (e as Error).message }),
  });

  const reorderMut = useMutation({
    mutationFn: (items: { id: number; orden: number }[]) => trabajosAdminApi.reorder(items),
    onError: (e) => toast.error("Error reordenando", { description: (e as Error).message }),
  });

  function handleDragEnd(event: {
    active: { id: number | string };
    over: { id: number | string } | null;
  }) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setTrabajos((prev) => {
      const oldIdx = prev.findIndex((t) => t.id === active.id);
      const newIdx = prev.findIndex((t) => t.id === over.id);
      const reordered = arrayMove(prev, oldIdx, newIdx).map((t, i) => ({ ...t, orden: i }));
      reorderMut.mutate(reordered.map((t) => ({ id: t.id, orden: t.orden })));
      return reordered;
    });
  }

  function openCreate() {
    setDialogMode({ mode: "create" });
    setDialogOpen(true);
  }

  function openEdit(t: EstudioTrabajo) {
    setDialogMode({ mode: "edit", trabajo: t });
    setDialogOpen(true);
  }

  function handleSaved(t: EstudioTrabajo) {
    setTrabajos((prev) => {
      const idx = prev.findIndex((x) => x.id === t.id);
      return idx >= 0 ? prev.map((x) => (x.id === t.id ? t : x)) : [...prev, t];
    });
    onChanged();
  }

  return (
    <>
      <Section title="Trabajos">
        <p className="text-xs text-muted-foreground">
          Producciones que aparecen en la sección "en acción" del estudio. Arrastrá para reordenar.
        </p>

        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={trabajos.map((t) => t.id)} strategy={verticalListSortingStrategy}>
            <div className="space-y-2">
              {trabajos.map((t) => (
                <SortableTrabajoCard
                  key={t.id}
                  trabajo={t}
                  onEdit={openEdit}
                  onDelete={(id) => deleteMut.mutate(id)}
                  onToggleActivo={(id, activo) => toggleMut.mutate({ id, activo })}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>

        {trabajos.length === 0 && (
          <EmptyState
            icon={<Film className="h-6 w-6" />}
            title="Sin trabajos cargados"
            sub="Agregá un trabajo con el botón de abajo."
          />
        )}

        <Button variant="outline" size="sm" onClick={openCreate}>
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          Agregar trabajo
        </Button>
      </Section>

      <TrabajoDialog
        open={dialogOpen}
        dialogMode={dialogMode}
        onClose={() => setDialogOpen(false)}
        onSaved={(t) => {
          handleSaved(t);
          setDialogOpen(false);
        }}
        availableCategorias={[...new Set(trabajos.flatMap((t) => t.categorias ?? []))]}
      />
    </>
  );
}
