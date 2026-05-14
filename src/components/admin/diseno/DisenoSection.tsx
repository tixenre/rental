/**
 * DisenoSection — "Cómo se ve el catálogo público".
 *
 * Por ahora una sola pieza: orden + visibilidad de las secciones de
 * categoría raíz. El admin arrastra para reordenar y togglea el ojo para
 * ocultar una sección sin borrarla.
 *
 * Distinto de `/admin/equipos/categorias` que es CRUD (renombrar, mover
 * hijos, borrar). Acá solo "qué se ve y en qué orden".
 */

import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GripVertical, Eye, EyeOff, Loader2 } from "lucide-react";
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

import { adminApi, type CategoriaAdmin } from "@/lib/admin/api";

export function DisenoSection() {
  const qc = useQueryClient();
  const catsQ = useQuery({
    queryKey: ["admin", "categorias-list"],
    queryFn: () => adminApi.adminListCategorias(),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "categorias-list"] });
    qc.invalidateQueries({ queryKey: ["categorias"] });
    qc.invalidateQueries({ queryKey: ["equipos"] });
  };

  const updateMut = useMutation({
    mutationFn: ({ id, ...patch }: { id: number; prioridad?: number; visible?: boolean }) =>
      adminApi.adminUpdateCategoria(id, patch),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });

  // Root categorias ordenadas por prioridad ASC.
  const roots = useMemo(() => {
    return [...(catsQ.data ?? [])]
      .filter((c) => c.parent_id == null)
      .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
  }, [catsQ.data]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIdx = roots.findIndex((c) => c.id === active.id);
    const newIdx = roots.findIndex((c) => c.id === over.id);
    if (oldIdx < 0 || newIdx < 0) return;
    const next = arrayMove(roots, oldIdx, newIdx);
    // Optimistic: actualizar cache para feedback instantáneo. Si falla, invalida.
    qc.setQueryData<CategoriaAdmin[]>(
      ["admin", "categorias-list"],
      (prev) => {
        if (!prev) return prev;
        const byId = new Map(next.map((c, i) => [c.id, (i + 1) * 10] as const));
        return prev.map((c) =>
          byId.has(c.id) ? { ...c, prioridad: byId.get(c.id)! } : c,
        );
      },
    );
    // Persistir todos los cambios en paralelo.
    Promise.all(
      next.map((c, i) => adminApi.adminUpdateCategoria(c.id, { prioridad: (i + 1) * 10 })),
    )
      .then(invalidate)
      .catch((e: Error) => {
        toast.error(e.message);
        invalidate();
      });
  };

  const toggleVisible = (c: CategoriaAdmin) => {
    updateMut.mutate({ id: c.id, visible: !c.visible });
  };

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <header>
        <h2 className="font-display text-lg text-ink">Secciones del catálogo</h2>
        <p className="text-xs text-muted-foreground">
          Arrastrá para cambiar el orden en que aparecen en el catálogo público. Usá el
          ojo para ocultar una categoría sin borrarla — vuelve cuando la prendés de nuevo.
        </p>
      </header>

      {catsQ.isLoading && (
        <div className="py-6 text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Cargando…
        </div>
      )}

      {!catsQ.isLoading && roots.length === 0 && (
        <p className="py-6 text-sm text-muted-foreground italic text-center">
          No hay categorías raíz todavía. Creálas en{" "}
          <code className="text-ink">/admin/equipos/categorias</code> primero.
        </p>
      )}

      {roots.length > 0 && (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={roots.map((c) => c.id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="border hairline rounded-md divide-y divide-muted/40">
              {roots.map((c) => (
                <SortableRow
                  key={c.id}
                  categoria={c}
                  onToggleVisible={() => toggleVisible(c)}
                  disabled={updateMut.isPending}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}
    </section>
  );
}

function SortableRow({
  categoria, onToggleVisible, disabled,
}: {
  categoria: CategoriaAdmin;
  onToggleVisible: () => void;
  disabled: boolean;
}) {
  const sortable = useSortable({ id: categoria.id });
  const style = {
    transform: CSS.Transform.toString(sortable.transform),
    transition: sortable.transition,
    opacity: sortable.isDragging ? 0.6 : 1,
  };

  const hidden = !categoria.visible;

  return (
    <div
      ref={sortable.setNodeRef}
      style={style}
      className={`flex items-center gap-3 px-3 py-3 transition ${
        hidden ? "bg-muted/30 opacity-70" : "hover:bg-muted/20"
      }`}
    >
      <button
        {...sortable.attributes}
        {...sortable.listeners}
        className="cursor-grab active:cursor-grabbing h-5 w-5 grid place-items-center text-muted-foreground hover:text-foreground shrink-0"
        title="Arrastrar para reordenar"
        aria-label={`Reordenar ${categoria.nombre}`}
      >
        <GripVertical className="h-4 w-4" />
      </button>

      <div className="flex-1 min-w-0">
        <div className={`truncate text-sm ${hidden ? "text-muted-foreground line-through" : "text-ink"}`}>
          {categoria.nombre}
        </div>
        <div className="text-[10px] text-muted-foreground tabular-nums">
          {categoria.total} {categoria.total === 1 ? "equipo" : "equipos"}
        </div>
      </div>

      <button
        onClick={onToggleVisible}
        disabled={disabled}
        className={`h-8 w-8 grid place-items-center rounded-md transition disabled:opacity-50 shrink-0 ${
          hidden
            ? "text-muted-foreground hover:text-ink hover:bg-muted"
            : "text-ink hover:bg-amber-soft"
        }`}
        title={hidden ? "Mostrar en el catálogo" : "Ocultar del catálogo"}
        aria-label={hidden ? `Mostrar ${categoria.nombre}` : `Ocultar ${categoria.nombre}`}
      >
        {hidden ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}
