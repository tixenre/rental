/**
 * SpecTemplatesSection — editor de templates de specs por categoría.
 *
 * Vive dentro de /admin/settings. Permite al admin gestionar el schema de
 * specs que aplica cuando crea/edita un equipo de cada categoría.
 *
 * Por categoría se puede:
 *  - Listar las specs definidas (spec_key, label, tipo, flags).
 *  - Agregar una nueva (modal con form).
 *  - Editar una existente (mismo modal).
 *  - Borrar una. (Las equipo_specs huérfanas NO se borran — quedan como extras.)
 *
 * Plan maestro docs/DISEÑO_SPECS.md §8 (riesgos): "editor de templates desde día 1"
 * como mitigación a templates mal definidos.
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
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
import { Label } from "@/design-system/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/design-system/ui/alert-dialog";

import { adminApi, type CategoriaAdmin, type SpecTemplate } from "@/lib/admin/api";
import { NombreTemplateBuilder } from "./NombreTemplateBuilder";
import {
  OrphansPanel,
  DestacadasCounter,
  SortableSpecRow,
  SpecTemplateFormModal,
} from "./SpecTemplatesSectionHelpers";

export function SpecTemplatesSection({
  fixedCategoriaId,
  showHeader = true,
}: {
  /** Si se pasa, oculta el selector de categoría y trabaja con esta. */
  fixedCategoriaId?: number;
  /** Mostrar header "Specs por categoría" + descripción. False cuando se
   *  embebe en otro contexto (ej. dialog dentro de Categorías). */
  showHeader?: boolean;
} = {}) {
  const [catId, setCatId] = useState<number | null>(fixedCategoriaId ?? null);
  const [editing, setEditing] = useState<SpecTemplate | "new" | null>(null);
  // Si abrimos "new" desde una sugerencia de orphan, este state pre-llena
  // el key + label en el modal. Null = creación desde cero.
  const [prefillFromOrphan, setPrefillFromOrphan] = useState<{
    key: string;
    sampleValues: string[];
  } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<SpecTemplate | null>(null);
  const qc = useQueryClient();

  const catsQ = useQuery({
    queryKey: ["admin", "categorias"],
    queryFn: () => adminApi.adminListCategorias(),
  });

  // Construir lista plana con path (raíz › hija) desde la lista flat del backend
  const catsFlat = useMemo(() => {
    const all = catsQ.data ?? [];
    const flat: { id: number; nombre: string; path: string; prioridad: number }[] = [];
    const roots = all
      .filter((c) => c.parent_id == null)
      .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
    for (const root of roots) {
      flat.push({ id: root.id, nombre: root.nombre, path: root.nombre, prioridad: root.prioridad });
      const hijos = all
        .filter((c) => c.parent_id === root.id)
        .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
      for (const h of hijos) {
        flat.push({
          id: h.id,
          nombre: h.nombre,
          path: `${root.nombre} › ${h.nombre}`,
          prioridad: h.prioridad,
        });
      }
    }
    return flat;
  }, [catsQ.data]);

  const resumenQ = useQuery({
    queryKey: ["admin", "spec-templates-resumen"],
    queryFn: () => adminApi.specTemplatesResumen(),
  });

  const templatesQ = useQuery({
    queryKey: ["admin", "spec-templates", catId],
    queryFn: () => adminApi.listSpecTemplates(catId!),
    enabled: catId != null,
  });

  // Specs huérfanas — keys que están en equipo_specs de equipos de esta
  // categoría pero no en el template. Las mostramos como sugerencias para
  // que el dueño las formalice manualmente en lugar de auto-extender el
  // template (#calidad-datos).
  const orphansQ = useQuery({
    queryKey: ["admin", "spec-templates-orphans", catId],
    queryFn: () => adminApi.listOrphanSpecs(catId!),
    enabled: catId != null,
    staleTime: 30_000,
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => adminApi.deleteSpecTemplate(id),
    onSuccess: () => {
      toast.success("Spec eliminada");
      qc.invalidateQueries({ queryKey: ["admin", "spec-templates", catId] });
      setConfirmDelete(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const reorderMut = useMutation({
    mutationFn: (items: { id: number; prioridad: number }[]) =>
      adminApi.reorderSpecTemplates(items),
    // Optimistic: actualizamos el cache local antes del response para que el
    // re-orden visual sea instantáneo. Si falla, invalidamos para refetch.
    onMutate: async (next) => {
      await qc.cancelQueries({ queryKey: ["admin", "spec-templates", catId] });
      const prev = qc.getQueryData<{ items: SpecTemplate[] }>(["admin", "spec-templates", catId]);
      if (prev) {
        const byId = new Map(next.map((n) => [n.id, n.prioridad] as const));
        qc.setQueryData<{ items: SpecTemplate[] }>(["admin", "spec-templates", catId], {
          items: prev.items
            .map((t) => ({ ...t, prioridad: byId.get(t.id) ?? t.prioridad }))
            .sort((a, b) => a.prioridad - b.prioridad || a.label.localeCompare(b.label)),
        });
      }
      return { prev };
    },
    onError: (e: Error, _next, ctx) => {
      if (ctx?.prev) {
        qc.setQueryData(["admin", "spec-templates", catId], ctx.prev);
      }
      toast.error(e.message);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["admin", "spec-templates", catId] });
    },
  });

  const items = templatesQ.data?.items ?? [];

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = items.findIndex((t) => t.id === active.id);
    const newIndex = items.findIndex((t) => t.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const next = arrayMove(items, oldIndex, newIndex);
    const updates = next.map((t, i) => ({ id: t.id, prioridad: (i + 1) * 10 }));
    reorderMut.mutate(updates);
  };

  return (
    <section
      className={
        showHeader ? "rounded-lg border hairline bg-background p-4 space-y-4" : "space-y-4"
      }
    >
      {showHeader && (
        <header className="space-y-1">
          <h2 className="font-display text-lg text-ink">Specs por categoría</h2>
          <p className="text-xs text-muted-foreground">
            Definí qué campos técnicos pide cada categoría al cargar un equipo. Estos mismos labels
            guían la IA al importar desde URL.
          </p>
        </header>
      )}

      {/* Selector de categoría — oculto cuando fixedCategoriaId */}
      {fixedCategoriaId == null && (
        <div className="flex items-end gap-2">
          <div className="flex-1 max-w-md">
            <Label htmlFor="cat-select" className="text-xs">
              Categoría
            </Label>
            <Select
              value={catId != null ? String(catId) : ""}
              onValueChange={(v) => setCatId(Number(v))}
            >
              <SelectTrigger id="cat-select" className="h-9">
                <SelectValue placeholder="Elegir categoría…" />
              </SelectTrigger>
              <SelectContent>
                {catsFlat.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.path}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {catId != null && (
            <Button size="sm" onClick={() => setEditing("new")}>
              <Plus className="h-4 w-4 mr-1" /> Agregar spec
            </Button>
          )}
        </div>
      )}
      {fixedCategoriaId != null && (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setEditing("new")}>
            <Plus className="h-4 w-4 mr-1" /> Agregar spec
          </Button>
        </div>
      )}

      {/* Grid de categorías raíz como acceso rápido cuando no hay ninguna seleccionada */}
      {catId == null && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Hacé click en una categoría para ver y editar sus specs:
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {catsFlat
              .filter((c) => {
                const all = catsQ.data ?? [];
                const cat = all.find((x) => x.id === c.id);
                return cat?.parent_id == null;
              })
              .map((c) => {
                const count = resumenQ.data?.[c.id] ?? 0;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setCatId(c.id)}
                    className="rounded-md border hairline p-3 text-left text-sm transition hover:border-amber hover:bg-amber-soft/30 active:bg-amber-soft/50"
                  >
                    <div className="font-medium text-ink leading-snug">{c.nombre}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {count > 0 ? `${count} specs` : "sin specs aún"}
                    </div>
                  </button>
                );
              })}
          </div>
        </div>
      )}

      {catId != null && templatesQ.isLoading && (
        <div className="text-sm text-muted-foreground">Cargando…</div>
      )}

      {catId != null && !templatesQ.isLoading && items.length === 0 && (
        <div className="rounded-md border hairline border-dashed p-6 text-center text-sm text-muted-foreground">
          Esta categoría no tiene specs definidas. Agregá la primera con el botón "+".
        </div>
      )}

      {items.length > 0 && <DestacadasCounter items={items} />}

      {items.length > 0 && (
        <div className="rounded-md border hairline overflow-hidden">
          {/* Cabecera (alineada con las celdas — drag handle ocupa la primera columna). */}
          <div className="grid grid-cols-[24px_1fr_140px_minmax(0,1fr)_64px] items-center gap-2 bg-muted/40 px-3 py-2 text-xs text-muted-foreground md:grid-cols-[24px_1fr_140px_minmax(0,1fr)_64px]">
            <span aria-hidden />
            <span>Label / Key</span>
            <span>Tipo</span>
            <span className="hidden md:block">Flags</span>
            <span />
          </div>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext items={items.map((t) => t.id)} strategy={verticalListSortingStrategy}>
              <div className="divide-y hairline">
                {items.map((t) => (
                  <SortableSpecRow
                    key={t.id}
                    template={t}
                    onEdit={() => setEditing(t)}
                    onDelete={() => setConfirmDelete(t)}
                    disabled={reorderMut.isPending}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
          <p className="border-t hairline px-3 py-2 text-2xs text-muted-foreground bg-muted/20">
            Arrastrá una fila para cambiar el orden — la primera es la más prominente en el form de
            equipo y en la card del catálogo.
          </p>
        </div>
      )}

      {/* Sugerencias de orphans — specs cargados en equipos que no están en
          el template. el dueño decide si las formaliza o no. */}
      {catId != null && (orphansQ.data?.length ?? 0) > 0 && (
        <OrphansPanel
          orphans={orphansQ.data ?? []}
          onConvert={(o) => {
            setPrefillFromOrphan({ key: o.spec_key, sampleValues: o.sample_values });
            setEditing("new");
          }}
        />
      )}

      {/* Builder visual del template de nombre público — usa las specs de
          arriba como paleta. */}
      {catId != null && (
        <NombreTemplateBuilder
          categoriaId={catId}
          categoriaNombre={catsFlat.find((c) => c.id === catId)?.nombre ?? "Categoría"}
          initialTemplate={catsQ.data?.find((c) => c.id === catId)?.nombre_publico_template ?? null}
          templateSpecs={items}
        />
      )}

      {/* Modal crear/editar */}
      {editing && catId != null && (
        <SpecTemplateFormModal
          categoriaId={catId}
          template={editing === "new" ? null : editing}
          prefillKey={editing === "new" ? prefillFromOrphan?.key : undefined}
          prefillSampleValues={editing === "new" ? prefillFromOrphan?.sampleValues : undefined}
          categoriaPath={catsFlat.find((c) => c.id === catId)?.path ?? "Categoría"}
          onClose={() => {
            setEditing(null);
            setPrefillFromOrphan(null);
          }}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ["admin", "spec-templates", catId] });
            qc.invalidateQueries({ queryKey: ["admin", "spec-templates-orphans", catId] });
            setEditing(null);
            setPrefillFromOrphan(null);
          }}
        />
      )}

      {/* Confirmación eliminar */}
      <AlertDialog open={!!confirmDelete} onOpenChange={(v) => !v && setConfirmDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminar spec del template</AlertDialogTitle>
            <AlertDialogDescription>
              Vas a borrar <strong>{confirmDelete?.label}</strong> ({confirmDelete?.spec_key}) del
              template de esta categoría. Los valores ya cargados en equipos NO se borran: quedan
              como "extras" sin schema (los podés ver en la ficha del equipo).
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => confirmDelete && deleteMut.mutate(confirmDelete.id)}
              disabled={deleteMut.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

// Re-export type for consumers
export type { CategoriaAdmin };
