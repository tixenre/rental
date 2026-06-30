/**
 * DisenoSection — "Cómo se ve el catálogo público".
 *
 * Orden + visibilidad de las categorías del catálogo público. El admin
 * arrastra las RAÍCES para reordenarlas y togglea el ojo para ocultar
 * cualquier categoría (raíz, subcategoría o nieto) sin borrarla. Lo oculto
 * desaparece del mosaico "Buscá por categorías", de los tabs y de la
 * navegación pública (el backend filtra `visible` en /api/categorias).
 *
 * Distinto de `/admin/equipos/categorias` que es CRUD (renombrar, mover
 * hijos, borrar). Acá solo "qué se ve y en qué orden".
 */

import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GripVertical, Eye, EyeOff } from "lucide-react";
import { Spinner } from "@/design-system/ui/spinner";
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
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { adminApi, type CategoriaAdmin } from "@/lib/admin/api";

/** Fila aplanada del árbol para render: la categoría + su profundidad. */
type TreeRow = { cat: CategoriaAdmin; depth: number };

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

  const all = useMemo(() => catsQ.data ?? [], [catsQ.data]);

  // Hijos por parent_id, ordenados por prioridad ASC y luego nombre.
  const childrenByParent = useMemo(() => {
    const m = new Map<number | null, CategoriaAdmin[]>();
    for (const c of all) {
      const key = c.parent_id ?? null;
      if (!m.has(key)) m.set(key, []);
      m.get(key)!.push(c);
    }
    for (const arr of m.values()) {
      arr.sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
    }
    return m;
  }, [all]);

  // Raíces ordenadas (lo que el admin arrastra para reordenar).
  const roots = useMemo(() => childrenByParent.get(null) ?? [], [childrenByParent]);

  /** Filas aplanadas en orden de árbol bajo una raíz (children + grandchildren). */
  const descendantRows = (rootId: number): TreeRow[] => {
    const out: TreeRow[] = [];
    const walk = (parentId: number, depth: number) => {
      for (const child of childrenByParent.get(parentId) ?? []) {
        out.push({ cat: child, depth });
        walk(child.id, depth + 1);
      }
    };
    walk(rootId, 1);
    return out;
  };

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
    qc.setQueryData<CategoriaAdmin[]>(["admin", "categorias-list"], (prev) => {
      if (!prev) return prev;
      const byId = new Map(next.map((c, i) => [c.id, (i + 1) * 10] as const));
      return prev.map((c) => (byId.has(c.id) ? { ...c, prioridad: byId.get(c.id)! } : c));
    });
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
          Arrastrá las categorías raíz para cambiar el orden en que aparecen en el catálogo público.
          Usá el ojo para ocultar cualquier categoría —raíz o subcategoría— sin borrarla; lo oculto
          desaparece del mosaico, los tabs y la navegación. Vuelve cuando la prendés de nuevo.
        </p>
      </header>

      {catsQ.isLoading && (
        <div className="py-6 text-sm text-muted-foreground flex items-center gap-2">
          <Spinner size="sm" /> Cargando…
        </div>
      )}

      {!catsQ.isLoading && roots.length === 0 && (
        <p className="py-6 text-sm text-muted-foreground italic text-center">
          No hay categorías raíz todavía. Creálas en{" "}
          <code className="text-ink">/admin/equipos/categorias</code> primero.
        </p>
      )}

      {roots.length > 0 && (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={roots.map((c) => c.id)} strategy={verticalListSortingStrategy}>
            <div className="border hairline rounded-md divide-y divide-muted/40">
              {roots.map((root) => (
                <div key={root.id}>
                  <SortableRow
                    categoria={root}
                    onToggleVisible={() => toggleVisible(root)}
                    disabled={updateMut.isPending}
                  />
                  {descendantRows(root.id).map(({ cat, depth }) => (
                    <PlainRow
                      key={cat.id}
                      categoria={cat}
                      depth={depth}
                      onToggleVisible={() => toggleVisible(cat)}
                      disabled={updateMut.isPending}
                    />
                  ))}
                </div>
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}
    </section>
  );
}

/** Botón de ojo visible/oculto, compartido entre raíces y subcategorías. */
function VisibilityToggle({
  hidden,
  nombre,
  onToggle,
  disabled,
}: {
  hidden: boolean;
  nombre: string;
  onToggle: () => void;
  disabled: boolean;
}) {
  return (
    <button
      onClick={onToggle}
      disabled={disabled}
      className={`h-8 w-8 grid place-items-center rounded-md transition disabled:opacity-50 shrink-0 ${
        hidden
          ? "text-muted-foreground hover:text-ink hover:bg-muted"
          : "text-ink hover:bg-amber-soft"
      }`}
      title={hidden ? "Mostrar en el catálogo" : "Ocultar del catálogo"}
      aria-label={hidden ? `Mostrar ${nombre}` : `Ocultar ${nombre}`}
    >
      {hidden ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
    </button>
  );
}

function SortableRow({
  categoria,
  onToggleVisible,
  disabled,
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
        <div
          className={`truncate text-sm ${hidden ? "text-muted-foreground line-through" : "text-ink"}`}
        >
          {categoria.nombre}
        </div>
        <div className="text-2xs text-muted-foreground tabular-nums">
          {categoria.total} {categoria.total === 1 ? "equipo" : "equipos"}
        </div>
      </div>

      <VisibilityToggle
        hidden={hidden}
        nombre={categoria.nombre}
        onToggle={onToggleVisible}
        disabled={disabled}
      />
    </div>
  );
}

/** Fila de subcategoría/nieto: sin drag, indentada por profundidad, con ojo. */
function PlainRow({
  categoria,
  depth,
  onToggleVisible,
  disabled,
}: {
  categoria: CategoriaAdmin;
  depth: number;
  onToggleVisible: () => void;
  disabled: boolean;
}) {
  const hidden = !categoria.visible;

  return (
    <div
      className={`flex items-center gap-3 px-3 py-2 transition ${
        hidden ? "bg-muted/30 opacity-70" : "hover:bg-muted/20"
      }`}
      style={{ paddingLeft: 12 + depth * 24 }}
    >
      <span aria-hidden className="shrink-0 text-muted-foreground/60 select-none text-xs">
        └
      </span>

      <div className="flex-1 min-w-0">
        <div
          className={`truncate text-sm ${hidden ? "text-muted-foreground line-through" : "text-ink"}`}
        >
          {categoria.nombre}
        </div>
        <div className="text-2xs text-muted-foreground tabular-nums">
          {categoria.total} {categoria.total === 1 ? "equipo" : "equipos"}
        </div>
      </div>

      <VisibilityToggle
        hidden={hidden}
        nombre={categoria.nombre}
        onToggle={onToggleVisible}
        disabled={disabled}
      />
    </div>
  );
}
