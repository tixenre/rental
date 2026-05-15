import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Sparkles, Library, AlertCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import {
  adminApi,
  type SpecDefinition,
  type SpecDefinitionInput,
  type SpecTipo,
} from "@/lib/admin/api";

export const Route = createLazyFileRoute("/admin/specs/definitions")({
  component: SpecDefinitionsPage,
});

const TIPO_LABEL: Record<SpecTipo, string> = {
  string: "Texto",
  number: "Número",
  rango: "Rango (min-max)",
  wxh: "Dos medidas (×)",
  wxhxd: "Tres medidas (×)",
  multi_enum: "Lista (varios)",
  enum: "Opciones",
  bool: "Sí/No",
};

function SpecDefinitionsPage() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<SpecDefinition | "new" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<SpecDefinition | null>(null);

  const listQ = useQuery({
    queryKey: ["admin", "spec-definitions"],
    queryFn: () => adminApi.listSpecDefinitions(),
    staleTime: 30_000,
  });

  const delMut = useMutation({
    mutationFn: (id: number) => adminApi.deleteSpecDefinition(id),
    onSuccess: () => {
      toast.success("Definición borrada");
      qc.invalidateQueries({ queryKey: ["admin", "spec-definitions"] });
      setConfirmDelete(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const items = listQ.data?.items ?? [];

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-5xl mx-auto">
      <header className="flex items-end justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Back-office › Specs
          </div>
          <h1 className="font-display text-3xl text-ink flex items-center gap-2">
            <Library className="h-6 w-6 text-amber" />
            Catálogo global de specs
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Definiciones únicas de specs (montura, formato, etc.). Cada una
            puede asignarse a una o más categorías. Editar acá afecta a todas
            las categorías que la usan.
          </p>
        </div>
        <Button onClick={() => setEditing("new")}>
          <Plus className="h-4 w-4 mr-1" /> Nueva definición
        </Button>
      </header>

      {listQ.isLoading && (
        <div className="text-sm text-muted-foreground">Cargando…</div>
      )}

      {!listQ.isLoading && items.length === 0 && (
        <div className="rounded-md border hairline border-dashed p-6 text-center text-sm text-muted-foreground">
          No hay definiciones todavía. El seed las crea al iniciar el backend
          desde <code className="font-mono">backend/seeds/spec_templates.py</code>,
          o creá la primera con el botón "Nueva definición".
        </div>
      )}

      {items.length > 0 && (
        <div className="rounded-md border hairline overflow-hidden">
          <div className="grid grid-cols-[1fr_140px_minmax(0,1.2fr)_72px_72px_72px] items-center gap-2 bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            <span>Spec key / label</span>
            <span>Tipo</span>
            <span className="hidden md:block">Detalle</span>
            <span className="text-right">Usos</span>
            <span className="text-right">Compat</span>
            <span />
          </div>
          <div className="divide-y hairline">
            {items.map((def) => (
              <DefinitionRow
                key={def.id}
                def={def}
                onEdit={() => setEditing(def)}
                onDelete={() => setConfirmDelete(def)}
              />
            ))}
          </div>
        </div>
      )}

      {editing && (
        <DefinitionFormModal
          definition={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ["admin", "spec-definitions"] });
            setEditing(null);
          }}
        />
      )}

      <AlertDialog open={!!confirmDelete} onOpenChange={(v) => !v && setConfirmDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Borrar definición</AlertDialogTitle>
            <AlertDialogDescription>
              Vas a borrar <strong>{confirmDelete?.label}</strong> (
              <code className="font-mono">{confirmDelete?.spec_key}</code>) del
              catálogo global. Solo funciona si la spec NO está asignada a
              ninguna categoría y NO tiene valores cargados en equipos —
              sino el backend rechaza con 409.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => confirmDelete && delMut.mutate(confirmDelete.id)}
              disabled={delMut.isPending}
            >
              {delMut.isPending ? "Borrando…" : "Borrar"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function DefinitionRow({
  def, onEdit, onDelete,
}: {
  def: SpecDefinition;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="grid grid-cols-[1fr_140px_minmax(0,1.2fr)_72px_72px_72px] items-center gap-2 px-3 py-2 text-sm hover:bg-muted/20">
      <div className="min-w-0">
        <div className="font-display text-ink truncate">{def.label}</div>
        <div className="font-mono text-[10px] text-muted-foreground truncate">{def.spec_key}</div>
      </div>
      <div className="text-xs text-muted-foreground">
        {TIPO_LABEL[def.tipo]}
        {def.unidad && <span className="text-muted-foreground/70"> · {def.unidad}</span>}
      </div>
      <div className="hidden md:block text-[10px] text-muted-foreground truncate">
        {def.tipo === "enum" || def.tipo === "multi_enum"
          ? (def.enum_options ?? []).join(", ")
          : (def.ayuda ?? "")}
      </div>
      <div className="text-right text-xs tabular-nums text-muted-foreground">
        {def.uso_categorias ?? 0}c · {def.uso_equipos ?? 0}e
      </div>
      <div className="text-right">
        {def.es_compatibilidad && (
          <Badge variant="secondary" className="text-[9px]">
            <Sparkles className="h-2.5 w-2.5 mr-0.5" /> compat
          </Badge>
        )}
      </div>
      <div className="flex justify-end gap-1">
        <button onClick={onEdit} className="rounded p-1 hover:bg-muted/50" title="Editar">
          <Pencil className="h-3.5 w-3.5" />
        </button>
        <button onClick={onDelete} className="rounded p-1 hover:bg-destructive/10 text-destructive" title="Borrar">
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

function DefinitionFormModal({
  definition, onClose, onSaved,
}: {
  definition: SpecDefinition | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isNew = definition == null;
  const [form, setForm] = useState<SpecDefinitionInput>({
    spec_key: definition?.spec_key ?? "",
    label: definition?.label ?? "",
    tipo: definition?.tipo ?? "string",
    unidad: definition?.unidad ?? "",
    enum_options: definition?.enum_options ?? [],
    ayuda: definition?.ayuda ?? "",
    es_compatibilidad: definition?.es_compatibilidad ?? false,
  });
  const [enumInput, setEnumInput] = useState((definition?.enum_options ?? []).join(", "));
  const [busy, setBusy] = useState(false);

  async function handleSave() {
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
    const wantsEnum = form.tipo === "enum" || form.tipo === "multi_enum";
    const enumArr = wantsEnum
      ? enumInput.split(",").map((s) => s.trim()).filter(Boolean)
      : null;
    if (wantsEnum && (!enumArr || enumArr.length === 0)) {
      toast.error("Para tipo enum / lista tenés que listar al menos una opción");
      return;
    }
    const wantsUnidad = form.tipo === "rango" || form.tipo === "wxh" || form.tipo === "wxhxd";
    if (wantsUnidad && !(form.unidad ?? "").trim()) {
      toast.error("Para este tipo la unidad es obligatoria (mm, px, °, kg…).");
      return;
    }

    setBusy(true);
    try {
      const payload: SpecDefinitionInput = {
        spec_key: trimmedKey,
        label: trimmedLabel,
        tipo: form.tipo,
        unidad: form.unidad?.trim() || null,
        enum_options: enumArr,
        ayuda: form.ayuda?.trim() || null,
        es_compatibilidad: form.es_compatibilidad,
      };
      if (isNew) {
        await adminApi.createSpecDefinition(payload);
        toast.success("Definición creada");
      } else {
        await adminApi.updateSpecDefinition(definition!.id, payload);
        toast.success("Definición actualizada");
      }
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
    >
      <div
        className="w-full max-w-xl rounded-lg bg-background border hairline shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="border-b hairline px-4 py-3">
          <div className="font-display text-base text-ink">
            {isNew ? "Nueva definición" : "Editar definición"}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Cambios afectan a todas las categorías que usan esta spec.
          </p>
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

          <div>
            <Label className="text-xs">Tipo</Label>
            <Select
              value={form.tipo}
              onValueChange={(v: SpecTipo) => setForm({ ...form, tipo: v })}
            >
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {(["string", "number", "rango", "wxh", "wxhxd", "enum", "multi_enum", "bool"] as SpecTipo[]).map((t) => (
                  <SelectItem key={t} value={t}>{TIPO_LABEL[t]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {(form.tipo === "number" || form.tipo === "rango" || form.tipo === "wxh" || form.tipo === "wxhxd") && (
            <div>
              <Label className="text-xs">
                Unidad {form.tipo !== "number" && <span className="text-destructive">*</span>}
                {form.tipo === "number" && (
                  <span className="text-muted-foreground font-normal"> (opcional)</span>
                )}
              </Label>
              <Input
                value={form.unidad ?? ""}
                onChange={(e) => setForm({ ...form, unidad: e.target.value })}
                placeholder="ej. mm, px, kg, °"
              />
            </div>
          )}

          {(form.tipo === "enum" || form.tipo === "multi_enum") && (
            <div>
              <Label className="text-xs">Opciones (separadas por coma)</Label>
              <Input
                value={enumInput}
                onChange={(e) => setEnumInput(e.target.value)}
                placeholder={form.tipo === "multi_enum" ? "ej. Wi-Fi, USB-C, SDI" : "ej. E, RF, EF, MFT, PL"}
              />
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

          <label className="flex items-start gap-2 cursor-pointer rounded-md border hairline border-amber/30 bg-amber-soft/30 p-2">
            <input
              type="checkbox"
              checked={!!form.es_compatibilidad}
              onChange={(e) => setForm({ ...form, es_compatibilidad: e.target.checked })}
              className="mt-0.5 h-4 w-4"
            />
            <div className="text-xs">
              <div className="font-medium text-ink flex items-center gap-1">
                <Sparkles className="h-3 w-3 text-amber" />
                Driver de compatibilidad
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                Si está marcada, equipos con el mismo valor en esta spec se
                consideran compatibles (futuro: GET /equipos/&#123;id&#125;/compatibles).
                Útil para montura, conectividad, formato de memoria.
              </div>
            </div>
          </label>

          {!isNew && (
            <div className="rounded-md border hairline border-amber/30 bg-amber-soft/30 p-2 text-[11px] flex gap-2">
              <AlertCircle className="h-3.5 w-3.5 shrink-0 text-amber-700 mt-0.5" />
              <span className="text-muted-foreground">
                Cambiar <strong>tipo</strong> está bloqueado si hay equipos con valores cargados.
                Cambiar <strong>label</strong> o <strong>unidad</strong> sí se permite — afecta a todas las categorías que usan esta spec.
              </span>
            </div>
          )}
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
