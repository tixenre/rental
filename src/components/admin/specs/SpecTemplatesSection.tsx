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
  type SpecTemplate,
  type SpecTemplateInput,
  type SpecTipo,
} from "@/lib/admin/api";

const TIPO_LABEL: Record<SpecTipo, string> = {
  string: "Texto",
  number: "Número",
  enum: "Opciones (enum)",
  bool: "Sí/No",
};

export function SpecTemplatesSection() {
  const [catId, setCatId] = useState<number | null>(null);
  const [editing, setEditing] = useState<SpecTemplate | "new" | null>(null);
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
    <section className="rounded-lg border hairline bg-background p-4 space-y-4">
      <header className="space-y-1">
        <h2 className="font-display text-lg text-ink">Specs por categoría</h2>
        <p className="text-xs text-muted-foreground">
          Definí qué campos técnicos pide cada categoría al cargar un equipo. Estos
          mismos labels guían la IA al importar desde URL.
        </p>
      </header>

      {/* Selector de categoría */}
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
        <div className="rounded-md border hairline overflow-hidden">
          {/* Cabecera (alineada con las celdas — drag handle ocupa la primera columna). */}
          <div className="grid grid-cols-[24px_1fr_140px_minmax(0,1fr)_56px_64px] items-center gap-2 bg-muted/40 px-3 py-2 text-xs text-muted-foreground md:grid-cols-[24px_1fr_140px_minmax(0,1fr)_56px_64px]">
            <span aria-hidden />
            <span>Label / Key</span>
            <span>Tipo</span>
            <span className="hidden md:block">Flags</span>
            <span className="text-right">Prio</span>
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

      {/* Modal crear/editar */}
      {editing && catId != null && (
        <SpecTemplateFormModal
          categoriaId={catId}
          template={editing === "new" ? null : editing}
          categoriaPath={catsFlat.find((c) => c.id === catId)?.path ?? "Categoría"}
          onClose={() => setEditing(null)}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ["admin", "spec-templates", catId] });
            setEditing(null);
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
      className="grid grid-cols-[24px_1fr_140px_minmax(0,1fr)_56px_64px] items-center gap-2 px-3 py-2 text-sm hover:bg-muted/20"
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
        {template.tipo === "number" && template.unidad ? ` · ${template.unidad}` : ""}
        {template.tipo === "enum" && template.enum_options ? (
          <div className="text-[10px] text-muted-foreground truncate">
            {template.enum_options.join(", ")}
          </div>
        ) : null}
      </div>

      <div className="hidden md:flex flex-wrap gap-1 text-[10px] min-w-0">
        {template.destacado && <Badge tone="amber">destacado</Badge>}
        {template.obligatorio && <Badge>obligatorio</Badge>}
        {template.visible_en_nombre && <Badge>en nombre</Badge>}
        {template.visible_en_card && <Badge>en card</Badge>}
        {template.visible_en_filtros && <Badge>en filtros</Badge>}
      </div>
      <div className="md:hidden" aria-hidden />

      <div className="text-right text-xs tabular-nums text-muted-foreground">
        {template.prioridad}
      </div>

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
  categoriaId, template, categoriaPath, onClose, onSaved,
}: {
  categoriaId: number;
  template: SpecTemplate | null;
  categoriaPath: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isNew = template == null;
  const [form, setForm] = useState<SpecTemplateInput>({
    spec_key: template?.spec_key ?? "",
    label: template?.label ?? "",
    tipo: template?.tipo ?? "string",
    unidad: template?.unidad ?? "",
    enum_options: template?.enum_options ?? [],
    prioridad: template?.prioridad ?? 100,
    visible_en_card: template?.visible_en_card ?? false,
    visible_en_filtros: template?.visible_en_filtros ?? false,
    visible_en_nombre: template?.visible_en_nombre ?? false,
    obligatorio: template?.obligatorio ?? false,
    ayuda: template?.ayuda ?? "",
    destacado: template?.destacado ?? false,
  });
  const [enumInput, setEnumInput] = useState((template?.enum_options ?? []).join(", "));

  const createMut = useMutation({
    mutationFn: (input: SpecTemplateInput) => adminApi.createSpecTemplate(categoriaId, input),
    onSuccess: () => {
      toast.success("Spec creada");
      onSaved();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const updateMut = useMutation({
    mutationFn: (input: Partial<SpecTemplateInput>) =>
      adminApi.updateSpecTemplate(template!.id, input),
    onSuccess: () => {
      toast.success("Spec actualizada");
      onSaved();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const busy = createMut.isPending || updateMut.isPending;

  function handleSave() {
    const trimmedKey = form.spec_key.trim();
    const trimmedLabel = form.label.trim();
    if (!trimmedKey || !trimmedLabel) {
      toast.error("Spec key y label son obligatorios");
      return;
    }
    if (!/^[a-z][a-z0-9_]*$/.test(trimmedKey)) {
      toast.error("Spec key: solo minúsculas, números y _ (debe empezar con letra)");
      return;
    }
    const enumArr = form.tipo === "enum"
      ? enumInput.split(",").map((s) => s.trim()).filter(Boolean)
      : null;
    if (form.tipo === "enum" && (!enumArr || enumArr.length === 0)) {
      toast.error("Para tipo enum tenés que listar al menos una opción");
      return;
    }
    const payload: SpecTemplateInput = {
      ...form,
      spec_key: trimmedKey,
      label: trimmedLabel,
      unidad: form.unidad?.trim() || null,
      ayuda: form.ayuda?.trim() || null,
      enum_options: enumArr,
    };
    if (isNew) createMut.mutate(payload);
    else updateMut.mutate(payload);
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
              {isNew ? "Nueva spec" : "Editar spec"}
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
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Spec key (interno)</Label>
              <Input
                value={form.spec_key}
                onChange={(e) => setForm({ ...form, spec_key: e.target.value })}
                placeholder="ej. montura"
                disabled={!isNew}
                className="font-mono"
              />
              <p className="text-[10px] text-muted-foreground mt-1">
                {isNew ? "Inmutable después. Solo a-z 0-9 _" : "No se puede cambiar después de creado"}
              </p>
            </div>
            <div>
              <Label className="text-xs">Label visible</Label>
              <Input
                value={form.label}
                onChange={(e) => setForm({ ...form, label: e.target.value })}
                placeholder="ej. Montura"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Tipo</Label>
              <Select
                value={form.tipo}
                onValueChange={(v: SpecTipo) => setForm({ ...form, tipo: v })}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(["string", "number", "enum", "bool"] as SpecTipo[]).map((t) => (
                    <SelectItem key={t} value={t}>{TIPO_LABEL[t]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Prioridad</Label>
              <Input
                type="number"
                value={form.prioridad ?? 100}
                onChange={(e) => setForm({ ...form, prioridad: parseInt(e.target.value) || 100 })}
              />
              <p className="text-[10px] text-muted-foreground mt-1">Menor = aparece antes</p>
            </div>
          </div>

          {form.tipo === "number" && (
            <div>
              <Label className="text-xs">Unidad (opcional)</Label>
              <Input
                value={form.unidad ?? ""}
                onChange={(e) => setForm({ ...form, unidad: e.target.value })}
                placeholder="ej. mm, W, kg, fps"
              />
            </div>
          )}

          {form.tipo === "enum" && (
            <div>
              <Label className="text-xs">Opciones (separadas por coma)</Label>
              <Input
                value={enumInput}
                onChange={(e) => setEnumInput(e.target.value)}
                placeholder="ej. E, RF, EF, MFT, PL"
              />
              <p className="text-[10px] text-muted-foreground mt-1">
                Valores que aparecen en el dropdown del equipo. Case-sensitive.
              </p>
            </div>
          )}

          <div>
            <Label className="text-xs">Ayuda (opcional)</Label>
            <Input
              value={form.ayuda ?? ""}
              onChange={(e) => setForm({ ...form, ayuda: e.target.value })}
              placeholder="Texto que aparece bajo el input al cargar un equipo"
            />
          </div>

          <fieldset className="border hairline rounded-md p-3 space-y-2">
            <legend className="px-1 text-xs text-muted-foreground">Visibilidad</legend>
            <Toggle
              label="Spec destacada — aparece como quick fact en la fila del catálogo"
              checked={!!form.destacado}
              onChange={(v) => setForm({ ...form, destacado: v })}
            />
            <Toggle
              label="Obligatorio al crear equipo"
              checked={!!form.obligatorio}
              onChange={(v) => setForm({ ...form, obligatorio: v })}
            />
            <Toggle
              label="Aparece en el nombre público (Cámara Sony FX3 Montura E…)"
              checked={!!form.visible_en_nombre}
              onChange={(v) => setForm({ ...form, visible_en_nombre: v })}
            />
            <Toggle
              label="Aparece en la card del catálogo público"
              checked={!!form.visible_en_card}
              onChange={(v) => setForm({ ...form, visible_en_card: v })}
            />
            <Toggle
              label="Genera filtro en el catálogo público"
              checked={!!form.visible_en_filtros}
              onChange={(v) => setForm({ ...form, visible_en_filtros: v })}
            />
          </fieldset>
        </div>

        <footer className="border-t hairline px-4 py-3 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>Cancelar</Button>
          <Button onClick={handleSave} disabled={busy}>
            {busy ? "Guardando…" : isNew ? "Crear" : "Guardar"}
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
