/**
 * MarcasSection — gestión de marcas (carrusel público) con drag-drop.
 * Extraído de /admin/settings → /admin/equipos/marcas.
 */

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, GripVertical, X } from "lucide-react";
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

import { Input } from "@/components/ui/input";

import { adminApi, type MarcaAdmin } from "@/lib/admin/api";

export function MarcasSection() {
  const qc = useQueryClient();
  const listQ = useQuery({
    queryKey: ["admin", "marcas"],
    queryFn: () => adminApi.adminListMarcas(),
  });

  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<MarcaAdmin[]>([]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["admin", "marcas"] });
    qc.invalidateQueries({ queryKey: ["marcas"] });
    qc.invalidateQueries({ queryKey: ["equipos"] });
  };

  const updateMut = useMutation({
    mutationFn: ({ id, ...patch }: { id: number } & Partial<MarcaAdmin>) =>
      adminApi.adminUpdateMarca(id, patch),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });

  const reorderMut = useMutation({
    mutationFn: (reorder: { id: number; orden: number }[]) =>
      adminApi.adminReorderMarcas(reorder),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });

  const allMarcas = listQ.data?.items ?? [];

  useEffect(() => {
    if (allMarcas.length > 0 && selected.length === 0) {
      const visibles = allMarcas.filter((m) => m.visible).sort((a, b) => a.orden - b.orden);
      // Si ninguna está marcada como visible, mostrar todas en "Seleccionadas"
      // para que el usuario vea que existen y pueda ordenarlas.
      if (visibles.length > 0) {
        setSelected(visibles);
      } else {
        setSelected(allMarcas.sort((a, b) => a.nombre.localeCompare(b.nombre)));
      }
    }
  }, [allMarcas, selected.length]);

  const filteredAvailable = useMemo(() => {
    const f = search.trim().toLowerCase();
    const selectedIds = new Set(selected.map((m) => m.id));
    return allMarcas
      .filter((m) => !selectedIds.has(m.id) && m.nombre.toLowerCase().includes(f))
      .sort((a, b) => a.nombre.localeCompare(b.nombre));
  }, [allMarcas, selected, search]);

  const handleSelectMarca = (marca: MarcaAdmin) => {
    const nextOrden = Math.max(...selected.map((m) => m.orden), 99) + 1;
    setSelected([...selected, { ...marca, orden: nextOrden, visible: true }]);
  };

  const handleRemoveMarca = (id: number) => {
    const marca = selected.find((m) => m.id === id);
    if (marca) {
      updateMut.mutate({ id, visible: false });
    }
    setSelected(selected.filter((m) => m.id !== id));
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = selected.findIndex((m) => m.id === active.id);
    const newIndex = selected.findIndex((m) => m.id === over.id);

    const newOrder = arrayMove(selected, oldIndex, newIndex);
    setSelected(newOrder);

    const updates = newOrder.map((m, i) => ({ id: m.id, orden: i * 10 }));
    reorderMut.mutate(updates);
  };

  const toggleVisible = (id: number, currentVis: boolean) => {
    updateMut.mutate({ id, visible: !currentVis });
  };

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  return (
    <section className="rounded-lg border hairline bg-background p-4 space-y-3">
      <div>
        <h2 className="font-display text-lg text-ink">Marcas</h2>
        <p className="text-sm text-muted-foreground">
          Selecciona qué marcas quieres que aparezcan en el carrusel público y ordénalas con drag-drop.
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

      {!listQ.isLoading && (
        <div className="grid grid-cols-2 gap-4">
          {/* Disponibles */}
          <div className="space-y-2">
            <div>
              <label className="text-xs uppercase tracking-wide text-muted-foreground">
                Disponibles
              </label>
              <Input
                placeholder="Buscar marca…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 mt-1"
              />
            </div>
            <div className="border hairline rounded-md p-2 space-y-1 max-h-96 overflow-auto">
              {allMarcas.length === 0 ? (
                <div className="text-xs text-muted-foreground py-4 text-center">
                  No hay marcas aún. Se crean automáticamente cuando agregás equipos.
                </div>
              ) : filteredAvailable.length > 0 ? (
                filteredAvailable.map((marca) => (
                  <button
                    key={marca.id}
                    onClick={() => handleSelectMarca(marca)}
                    className="w-full text-left flex items-center gap-2 rounded px-2 py-1.5 hover:bg-muted transition text-sm"
                  >
                    {marca.logo_url && (
                      <img
                        src={marca.logo_url}
                        alt={marca.nombre}
                        className="h-5 w-5 object-contain"
                        onError={(e) => (e.currentTarget.style.display = "none")}
                      />
                    )}
                    <span className="flex-1">{marca.nombre}</span>
                    <span className="text-xs text-muted-foreground">({marca.total})</span>
                  </button>
                ))
              ) : (
                <div className="text-xs text-muted-foreground py-2 text-center">
                  {search ? "Sin resultados" : "Todas seleccionadas"}
                </div>
              )}
            </div>
          </div>

          {/* Seleccionadas (con drag-drop) */}
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-wide text-muted-foreground">
              Seleccionadas ({selected.length})
            </label>
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext
                items={selected.map((m) => m.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="border hairline rounded-md p-2 space-y-1 max-h-96 overflow-auto">
                  {selected.length > 0 ? (
                    selected.map((marca) => (
                      <SortableMarcaItem
                        key={marca.id}
                        marca={marca}
                        onRemove={() => handleRemoveMarca(marca.id)}
                        onToggleVisible={() => toggleVisible(marca.id, marca.visible)}
                        disabled={updateMut.isPending || reorderMut.isPending}
                      />
                    ))
                  ) : (
                    <div className="text-xs text-muted-foreground py-2 text-center">
                      Sin marcas seleccionadas
                    </div>
                  )}
                </div>
              </SortableContext>
            </DndContext>
          </div>
        </div>
      )}
    </section>
  );
}

function SortableMarcaItem({
  marca, onRemove, onToggleVisible, disabled,
}: {
  marca: MarcaAdmin;
  onRemove: () => void;
  onToggleVisible: () => void;
  disabled: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: marca.id });
  const style = { transform: CSS.Transform.toString(transform), transition };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 rounded px-2 py-1.5 bg-muted/50 text-sm group"
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing h-4 w-4 text-muted-foreground hover:text-foreground flex-shrink-0"
        title="Arrastrar para reordenar"
      >
        <GripVertical className="h-4 w-4" />
      </button>

      {marca.logo_url && (
        <img
          src={marca.logo_url}
          alt={marca.nombre}
          className="h-5 w-5 object-contain flex-shrink-0"
          onError={(e) => (e.currentTarget.style.display = "none")}
        />
      )}

      <div className="flex-1 min-w-0">
        <div className="truncate text-ink">{marca.nombre}</div>
        <div className="text-[10px] text-muted-foreground">{marca.total} equipos</div>
      </div>

      <input
        type="checkbox"
        checked={marca.visible}
        onChange={onToggleVisible}
        disabled={disabled}
        className="h-4 w-4 flex-shrink-0 cursor-pointer"
        title={marca.visible ? "Ocultar" : "Mostrar"}
      />

      <button
        onClick={onRemove}
        disabled={disabled}
        className="h-4 w-4 flex-shrink-0 text-muted-foreground hover:text-destructive transition disabled:opacity-50"
        title="Remover"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
