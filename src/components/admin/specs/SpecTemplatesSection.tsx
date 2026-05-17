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
import { Plus, Trash2, Pencil, X, GripVertical } from "lucide-react";
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
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import {
  adminApi,
  type CategoriaAdmin,
  type RolCompatibilidad,
  type SpecDefinition,
  type SpecTemplate,
  type SpecTipo,
} from "@/lib/admin/api";
import { NombreTemplateBuilder } from "./NombreTemplateBuilder";

const TIPO_LABEL: Record<SpecTipo, string> = {
  string: "Texto",
  number: "Número",
  rango: "Rango (un valor o dos, separados por '-')",
  wxh: "Dos medidas (ancho × alto, ej. 6144×3240)",
  wxhxd: "Tres medidas (ancho × alto × prof, ej. 130×85×78)",
  multi_enum: "Lista de opciones (varios valores, ej. Wi-Fi, USB-C, SDI)",
  enum: "Opciones (enum)",
  bool: "Sí/No",
  tabla: "Tabla (filas con columnas configurables)",
};

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
  const [prefillFromOrphan, setPrefillFromOrphan] = useState<{ key: string; sampleValues: string[] } | null>(null);
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
    const roots = all.filter((c) => c.parent_id == null)
      .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
    for (const root of roots) {
      flat.push({ id: root.id, nombre: root.nombre, path: root.nombre, prioridad: root.prioridad });
      const hijos = all.filter((c) => c.parent_id === root.id)
        .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
      for (const h of hijos) {
        flat.push({ id: h.id, nombre: h.nombre, path: `${root.nombre} › ${h.nombre}`, prioridad: h.prioridad });
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
      const prev = qc.getQueryData<{ items: SpecTemplate[] }>([
        "admin", "spec-templates", catId,
      ]);
      if (prev) {
        const byId = new Map(next.map((n) => [n.id, n.prioridad] as const));
        qc.setQueryData<{ items: SpecTemplate[] }>(
          ["admin", "spec-templates", catId],
          {
            items: prev.items
              .map((t) => ({ ...t, prioridad: byId.get(t.id) ?? t.prioridad }))
              .sort((a, b) => a.prioridad - b.prioridad || a.label.localeCompare(b.label)),
          },
        );
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
    <section className={showHeader ? "rounded-lg border hairline bg-background p-4 space-y-4" : "space-y-4"}>
      {showHeader && (
        <header className="space-y-1">
          <h2 className="font-display text-lg text-ink">Specs por categoría</h2>
          <p className="text-xs text-muted-foreground">
            Definí qué campos técnicos pide cada categoría al cargar un equipo. Estos
            mismos labels guían la IA al importar desde URL.
          </p>
        </header>
      )}

      {/* Selector de categoría — oculto cuando fixedCategoriaId */}
      {fixedCategoriaId == null && (
        <div className="flex items-end gap-2">
          <div className="flex-1 max-w-md">
            <Label htmlFor="cat-select" className="text-xs">Categoría</Label>
            <Select
              value={catId != null ? String(catId) : ""}
              onValueChange={(v) => setCatId(Number(v))}
            >
              <SelectTrigger id="cat-select" className="h-9">
                <SelectValue placeholder="Elegir categoría…" />
              </SelectTrigger>
              <SelectContent>
                {catsFlat.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>{c.path}</SelectItem>
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
                    <div className="text-[11px] text-muted-foreground mt-0.5">
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

      {items.length > 0 && (
        <DestacadasCounter items={items} />
      )}

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
            <SortableContext
              items={items.map((t) => t.id)}
              strategy={verticalListSortingStrategy}
            >
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
          <p className="border-t hairline px-3 py-2 text-[10px] text-muted-foreground bg-muted/20">
            Arrastrá una fila para cambiar el orden — la primera es la más prominente
            en el form de equipo y en la card del catálogo.
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
              Vas a borrar <strong>{confirmDelete?.label}</strong> ({confirmDelete?.spec_key})
              del template de esta categoría. Los valores ya cargados en equipos NO se borran:
              quedan como "extras" sin schema (los podés ver en la ficha del equipo).
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

/** Panel con specs huérfanas — valores cargados en equipos cuyo spec_key no
 *  está en el template de la categoría. El dueño decide si formalizarlos.
 *  Evita que el sistema auto-extienda el template silenciosamente. */
function OrphansPanel({
  orphans,
  onConvert,
}: {
  orphans: { spec_key: string; count_equipos: number; sample_values: string[] }[];
  onConvert: (o: { spec_key: string; sample_values: string[] }) => void;
}) {
  return (
    <div className="rounded-md border hairline border-amber/30 bg-amber-soft/30 overflow-hidden">
      <header className="px-3 py-2 text-xs font-mono uppercase tracking-widest text-muted-foreground border-b hairline">
        Sugerencias del autocompletar — {orphans.length} {orphans.length === 1 ? "spec" : "specs"} cargadas en equipos que no están en el template
      </header>
      <ul className="divide-y hairline">
        {orphans.map((o) => (
          <li key={o.spec_key} className="flex items-center gap-3 px-3 py-2 text-sm">
            <div className="flex-1 min-w-0">
              <div className="font-mono text-xs text-ink">{o.spec_key}</div>
              <div className="text-[11px] text-muted-foreground">
                {o.count_equipos} {o.count_equipos === 1 ? "equipo" : "equipos"} ·
                {" "}ejemplos: {o.sample_values.slice(0, 3).map((v) => `"${v}"`).join(", ")}
              </div>
            </div>
            <Button size="sm" variant="outline" onClick={() => onConvert(o)}>
              Agregar al template
            </Button>
          </li>
        ))}
      </ul>
      <p className="px-3 py-2 text-[10px] text-muted-foreground bg-amber-soft/50">
        Estos specs vinieron del autocompletar o de cargas anteriores y quedaron como "custom"
        en cada equipo. Si querés que aparezcan formateados en todos los equipos de esta categoría,
        agregalos al template con el tipo y unidad correctos.
      </p>
    </div>
  );
}

/** Pequeño indicador en la cabecera de la tabla mostrando cuántas specs
 *  están marcadas como ficha técnica destacada. La idea es mantener el
 *  conjunto chico (≤4) — son los quick facts del catálogo público y si
 *  son demasiados la card se satura. Soft warning, no enforcement. */
function DestacadasCounter({ items }: { items: SpecTemplate[] }) {
  const total = items.filter((t) => t.destacado).length;
  const max = 4;
  const over = total > max;
  return (
    <div className={`flex items-center gap-2 text-xs ${over ? "text-amber-700" : "text-muted-foreground"}`}>
      <span className="font-mono uppercase tracking-widest">
        Ficha técnica destacada: {total}/{max}
      </span>
      {over && (
        <span>
          — recomendado {max} máx para no saturar la card del catálogo público.
        </span>
      )}
    </div>
  );
}

function Badge({ children, tone = "default" }: { children: React.ReactNode; tone?: "default" | "amber" }) {
  const cls = tone === "amber"
    ? "bg-amber/15 text-ink"
    : "bg-muted text-muted-foreground";
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 ${cls}`}>{children}</span>
  );
}

function SortableSpecRow({
  template, onEdit, onDelete, disabled,
}: {
  template: SpecTemplate;
  onEdit: () => void;
  onDelete: () => void;
  disabled: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: template.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="grid grid-cols-[24px_1fr_140px_minmax(0,1fr)_64px] items-center gap-2 px-3 py-2 text-sm hover:bg-muted/20"
    >
      <button
        {...attributes}
        {...listeners}
        disabled={disabled}
        className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground disabled:opacity-50"
        aria-label={`Reordenar ${template.label}`}
        title="Arrastrar para reordenar"
      >
        <GripVertical className="h-4 w-4" />
      </button>

      <div className="min-w-0">
        <div className="truncate text-ink">{template.label}</div>
        <div className="font-mono text-[10px] text-muted-foreground truncate">
          {template.spec_key}
        </div>
      </div>

      <div className="text-xs min-w-0">
        {TIPO_LABEL[template.tipo]}
        {(template.tipo === "number" || template.tipo === "rango" || template.tipo === "wxh" || template.tipo === "wxhxd") && template.unidad ? ` · ${template.unidad}` : ""}
        {template.tipo === "enum" && template.enum_options ? (
          <div className="text-[10px] text-muted-foreground truncate">
            {template.enum_options.join(", ")}
          </div>
        ) : null}
      </div>

      <div className="hidden md:flex flex-wrap gap-1 text-[10px] min-w-0">
        {template.destacado && <Badge tone="amber">★ ficha destacada</Badge>}
      </div>
      <div className="md:hidden" aria-hidden />

      <div className="flex justify-end gap-1">
        <button
          onClick={onEdit}
          className="rounded p-1 text-muted-foreground hover:bg-muted/50 hover:text-ink"
          aria-label="Editar"
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onDelete}
          className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
          aria-label="Eliminar"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Modal crear/editar
// ─────────────────────────────────────────────────────────────────────

function SpecTemplateFormModal({
  categoriaId, template, prefillKey, prefillSampleValues, categoriaPath, onClose, onSaved,
}: {
  categoriaId: number;
  template: SpecTemplate | null;
  /** Si se abre desde una sugerencia orphan, pre-llena la búsqueda con
   *  ese key para que sea fácil encontrar la spec correspondiente. */
  prefillKey?: string;
  /** Valores de ejemplo del orphan — útiles para que el dueño los vea
   *  mientras decide qué spec asignar. */
  prefillSampleValues?: string[];
  categoriaPath: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isNew = template == null;
  const qcInner = useQueryClient();

  // Modo ASIGNAR (isNew): el user elige una spec del catálogo global y
  // setea los flags por categoría. NO crea specs nuevas — ese flujo vive en
  // Gear Compatibility → Definiciones (fuente de verdad).
  // Modo EDITAR (!isNew): solo flags de la asignación; los campos globales
  // (label/tipo/unidad/enum_options/compat) se editan en Gear Compat.

  // Catálogo global de specs (para el picker en modo asignar).
  const defsQ = useQuery({
    queryKey: ["admin", "spec-definitions"],
    queryFn: () => adminApi.listSpecDefinitions(),
    enabled: isNew,
    staleTime: 30_000,
  });

  // En modo asignar: spec seleccionada del catálogo. Si vino prefillKey,
  // intentamos pre-seleccionarla automáticamente cuando carga la lista.
  const [selectedDefId, setSelectedDefId] = useState<number | null>(null);
  const [search, setSearch] = useState(prefillKey ?? "");

  // Si vino prefillKey y el catálogo cargó, pre-seleccionar la spec exacta.
  // (No deps en setSelectedDefId para evitar loops.)
  if (isNew && prefillKey && defsQ.data && selectedDefId == null) {
    const match = defsQ.data.items.find(
      (d) => d.spec_key === prefillKey || d.label.toLowerCase() === prefillKey.toLowerCase(),
    );
    if (match) setSelectedDefId(match.id);
  }

  // Flags de la asignación (per-categoría).
  const [flags, setFlags] = useState({
    prioridad: template?.prioridad ?? 100,
    destacado: template?.destacado ?? false,
    obligatorio: template?.obligatorio ?? false,
    visible_en_card: template?.visible_en_card ?? false,
    visible_en_nombre: template?.visible_en_nombre ?? false,
    rol_compatibilidad: (template?.rol_compatibilidad ?? null) as RolCompatibilidad,
  });
  const [busy, setBusy] = useState(false);

  // Specs disponibles para asignar = catálogo global - las que ya están
  // asignadas a esta categoría (vienen como hermanas de `template` en el
  // GET listSpecTemplates, pero acá filtramos client-side).
  const yaAsignadasIds = useQuery({
    queryKey: ["admin", "spec-templates", categoriaId, "ids-only"],
    queryFn: async () => {
      const r = await adminApi.listSpecTemplates(categoriaId);
      return new Set(r.items.map((t) => t.spec_def_id));
    },
    enabled: isNew,
    staleTime: 10_000,
  });

  const candidatas = useMemo(() => {
    const all = defsQ.data?.items ?? [];
    const ya = yaAsignadasIds.data ?? new Set<number>();
    const q = search.trim().toLowerCase();
    return all
      .filter((d) => !ya.has(d.id))
      .filter((d) => {
        if (!q) return true;
        return (
          d.label.toLowerCase().includes(q) ||
          d.spec_key.toLowerCase().includes(q)
        );
      })
      .sort((a, b) =>
        a.validado === b.validado
          ? a.label.localeCompare(b.label)
          : a.validado ? -1 : 1,
      );
  }, [defsQ.data, yaAsignadasIds.data, search]);

  // Spec del catálogo seleccionada (modo asignar) o derivada del template (edit).
  const specInfo: SpecDefinition | undefined = isNew
    ? defsQ.data?.items.find((d) => d.id === selectedDefId)
    : defsQ.data?.items.find((d) => d.id === template?.spec_def_id) ?? (template ? {
        id: template.spec_def_id,
        spec_key: template.spec_key,
        label: template.label,
        tipo: template.tipo,
        unidad: template.unidad,
        enum_options: template.enum_options,
        ayuda: template.ayuda,
        es_compatibilidad: template.es_compatibilidad,
        compatibilidad_modo: template.compatibilidad_modo,
        validado: false,
      } as SpecDefinition : undefined);

  const showRolField =
    specInfo?.es_compatibilidad &&
    specInfo?.compatibilidad_modo === "jerarquia" &&
    specInfo?.tipo === "enum";

  async function handleSave() {
    if (isNew && !selectedDefId) {
      toast.error("Seleccioná una spec del catálogo para asignar.");
      return;
    }
    setBusy(true);
    try {
      if (isNew && selectedDefId) {
        await adminApi.assignSpecToCategoria(categoriaId, {
          spec_def_id: selectedDefId,
          prioridad: flags.prioridad,
          destacado: flags.destacado,
          obligatorio: flags.obligatorio,
          visible_en_card: flags.visible_en_card,
          visible_en_filtros: true,
          visible_en_nombre: flags.visible_en_nombre,
          ayuda: null,
          rol_compatibilidad: showRolField ? flags.rol_compatibilidad : null,
        });
        toast.success("Spec asignada a la categoría");
      } else if (template) {
        await adminApi.updateSpecTemplate(template.id, {
          prioridad: flags.prioridad,
          destacado: flags.destacado,
          obligatorio: flags.obligatorio,
          visible_en_card: flags.visible_en_card,
          visible_en_nombre: flags.visible_en_nombre,
          rol_compatibilidad: showRolField ? flags.rol_compatibilidad : null,
        });
        toast.success("Asignación actualizada");
      }
      qcInner.invalidateQueries({ queryKey: ["admin", "spec-templates"] });
      qcInner.invalidateQueries({ queryKey: ["admin", "spec-definitions"] });
      onSaved();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="bg-background rounded-lg border hairline w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b hairline px-4 py-3">
          <div className="min-w-0">
            <div className="font-display text-base text-ink">
              {isNew ? "Asignar spec a categoría" : "Editar asignación"}
            </div>
            <div className="text-[11px] text-muted-foreground truncate">{categoriaPath}</div>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1.5 text-muted-foreground hover:bg-muted/50 hover:text-ink"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="p-4 space-y-3">
          {prefillKey && prefillSampleValues && prefillSampleValues.length > 0 && (
            <div className="rounded-md border hairline border-amber/30 bg-amber-soft/30 px-3 py-2 text-[11px]">
              <div className="font-mono uppercase tracking-widest text-muted-foreground mb-0.5">
                Sugerencia desde "{prefillKey}"
              </div>
              <div className="text-ink">
                Valores en equipos: {prefillSampleValues.map((v) => `"${v}"`).join(", ")}
              </div>
              <p className="text-muted-foreground mt-1 text-[10px]">
                Buscá una spec del catálogo que matchee, o creala en Gear Compatibility si no existe.
              </p>
            </div>
          )}

          {/* ── Modo ASIGNAR: picker del catálogo ───────────────────────── */}
          {isNew && (
            <>
              <div>
                <Label className="text-xs">Buscar spec en el catálogo</Label>
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Buscar por label o spec_key…"
                  className="font-mono"
                  autoFocus
                />
                <p className="text-[10px] text-muted-foreground mt-1">
                  Las specs validadas aparecen arriba. Si no encontrás la que buscás,
                  {" "}<a href="/admin/gear-compatibility" className="text-amber underline">creala en Gear Compatibility →</a>
                </p>
              </div>
              <div className="border hairline rounded-md max-h-64 overflow-y-auto divide-y hairline">
                {defsQ.isLoading && (
                  <div className="px-3 py-2 text-[11px] text-muted-foreground">Cargando…</div>
                )}
                {!defsQ.isLoading && candidatas.length === 0 && (
                  <div className="px-3 py-2 text-[11px] text-muted-foreground italic">
                    {search
                      ? "Ninguna spec disponible matchea la búsqueda."
                      : "Todas las specs del catálogo ya están asignadas a esta categoría."}
                  </div>
                )}
                {candidatas.map((d) => (
                  <button
                    type="button"
                    key={d.id}
                    onClick={() => setSelectedDefId(d.id)}
                    className={
                      "w-full text-left px-3 py-1.5 text-xs hover:bg-muted/30 " +
                      (selectedDefId === d.id ? "bg-amber-soft/40" : "")
                    }
                  >
                    <div className="flex items-center gap-1.5">
                      {d.validado && <span className="text-emerald-600">✓</span>}
                      <span className="text-ink font-medium">{d.label}</span>
                      <span className="font-mono text-[9px] text-muted-foreground">{d.spec_key}</span>
                      <span className="text-[9px] text-muted-foreground ml-auto">
                        {TIPO_LABEL[d.tipo]}{d.unidad ? ` · ${d.unidad}` : ""}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}

          {/* ── Spec seleccionada (info read-only) ──────────────────────── */}
          {specInfo && (
            <div className="rounded-md border hairline bg-muted/20 px-3 py-2 space-y-0.5">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-xs font-medium text-ink">{specInfo.label}</span>
                <span className="font-mono text-[9px] text-muted-foreground">{specInfo.spec_key}</span>
                <span className="text-[9px] text-muted-foreground">
                  · {TIPO_LABEL[specInfo.tipo]}{specInfo.unidad ? ` · ${specInfo.unidad}` : ""}
                </span>
                {specInfo.es_compatibilidad && (
                  <span className="text-[9px] bg-amber-soft/60 text-amber-800 px-1 rounded">
                    compat {specInfo.compatibilidad_modo}
                  </span>
                )}
              </div>
              {specInfo.tipo === "enum" || specInfo.tipo === "multi_enum" ? (
                <div className="text-[10px] text-muted-foreground">
                  Opciones: {(specInfo.enum_options ?? []).join(", ") || "—"}
                </div>
              ) : null}
              {specInfo.ayuda && (
                <div className="text-[10px] text-muted-foreground italic">{specInfo.ayuda}</div>
              )}
              <a
                href="/admin/gear-compatibility"
                className="text-[10px] text-amber underline inline-block"
              >
                Editar la definición global →
              </a>
            </div>
          )}

          {/* ── Flags de la asignación (per-categoría) ─────────────────── */}
          {(specInfo || !isNew) && (
            <fieldset className="border hairline rounded-md p-3 space-y-2">
              <legend className="px-1 text-xs text-muted-foreground">
                Flags para esta categoría
              </legend>
              <Toggle
                label="Ficha técnica destacada — aparece como quick fact en la card del catálogo público (recomendado máx 4 por categoría)"
                checked={flags.destacado}
                onChange={(v) => setFlags({ ...flags, destacado: v })}
              />
              <Toggle
                label="Visible en card del catálogo"
                checked={flags.visible_en_card}
                onChange={(v) => setFlags({ ...flags, visible_en_card: v })}
              />
              <Toggle
                label="Obligatorio al cargar el equipo"
                checked={flags.obligatorio}
                onChange={(v) => setFlags({ ...flags, obligatorio: v })}
              />
              {showRolField && (
                <div>
                  <Label className="text-xs">
                    Rol en compatibilidad jerárquica
                  </Label>
                  <Select
                    value={flags.rol_compatibilidad ?? "ninguno"}
                    onValueChange={(v) =>
                      setFlags({
                        ...flags,
                        rol_compatibilidad: v === "ninguno" ? null : (v as "contenedor" | "contenido"),
                      })
                    }
                  >
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ninguno">No participa</SelectItem>
                      <SelectItem value="contenedor">Contenedor (proyecta — ej. lente)</SelectItem>
                      <SelectItem value="contenido">Contenido (recibe — ej. sensor)</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    El modo jerárquico de la spec global decide; acá solo definís
                    cómo participa esta categoría.
                  </p>
                </div>
              )}
            </fieldset>
          )}
        </div>

        <footer className="border-t hairline px-4 py-3 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>Cancelar</Button>
          <Button onClick={handleSave} disabled={busy || (isNew && !selectedDefId)}>
            {busy ? "Guardando…" : isNew ? "Asignar" : "Guardar"}
          </Button>
        </footer>
      </div>
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 text-xs text-ink cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4"
      />
      <span>{label}</span>
    </label>
  );
}

// Re-export type for consumers
export type { CategoriaAdmin };
