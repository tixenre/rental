import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Sparkles, Library, AlertCircle, ArrowLeftRight, ListOrdered, CheckCircle2, Circle, Search, X } from "lucide-react";

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
  type CompatibilidadModo,
  type SpecDefinition,
  type SpecDefinitionInput,
  type SpecTipo,
} from "@/lib/admin/api";

export const Route = createLazyFileRoute("/admin/specs/definitions")({
  component: SpecDefinitionsPage,
});

/** Contenido reusable de la pantalla de definiciones de specs. Se exporta
 *  para que la pantalla unificada `/admin/gear-compatibility` lo embeba
 *  como tab sin duplicar lógica. */
export function SpecDefinitionsContent() {
  return <SpecDefinitionsPage embedded />;
}

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

function SpecDefinitionsPage({ embedded = false }: { embedded?: boolean } = {}) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<SpecDefinition | "new" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<SpecDefinition | null>(null);
  const [search, setSearch] = useState("");
  const [catFilter, setCatFilter] = useState<string | null>(null);   // nombre de categoría o "__sin__" o null
  const [soloValidadas, setSoloValidadas] = useState(false);

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

  // Toggle rápido del driver de compatibilidad desde la tabla. Si se activa
  // por primera vez, default a modo "exacta" (jerárquica requiere enum y se
  // configura desde el modal). Si ya está activo, lo apaga.
  const toggleCompatMut = useMutation({
    mutationFn: (def: SpecDefinition) =>
      adminApi.updateSpecDefinition(def.id, {
        es_compatibilidad: !def.es_compatibilidad,
        // Al apagar, no toco el modo (queda persistido para re-encender luego).
        ...(def.es_compatibilidad ? {} : { compatibilidad_modo: def.compatibilidad_modo ?? "exacta" }),
      }),
    onSuccess: (_data, def) => {
      toast.success(def.es_compatibilidad ? "Driver desactivado" : "Driver activado");
      qc.invalidateQueries({ queryKey: ["admin", "spec-definitions"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Toggle validado: marca/desmarca la spec como revisada. Las validadas
  // van arriba en la lista (sort en el backend).
  const toggleValidadoMut = useMutation({
    mutationFn: (def: SpecDefinition) =>
      adminApi.updateSpecDefinition(def.id, { validado: !def.validado }),
    onMutate: async (def) => {
      // Optimistic update: cambiamos el cache inmediatamente para que el
      // toggle se sienta instantáneo (es la acción más frecuente acá).
      await qc.cancelQueries({ queryKey: ["admin", "spec-definitions"] });
      const prev = qc.getQueryData<{ items: SpecDefinition[] }>(["admin", "spec-definitions"]);
      if (prev) {
        qc.setQueryData<{ items: SpecDefinition[] }>(["admin", "spec-definitions"], {
          items: prev.items
            .map((d) => (d.id === def.id ? { ...d, validado: !d.validado } : d))
            .sort((a, b) =>
              a.validado === b.validado
                ? a.label.localeCompare(b.label)
                : a.validado ? -1 : 1,
            ),
        });
      }
      return { prev };
    },
    onError: (e: Error, _def, ctx) => {
      if (ctx?.prev) qc.setQueryData(["admin", "spec-definitions"], ctx.prev);
      toast.error(e.message);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["admin", "spec-definitions"] });
    },
  });

  const allItems = listQ.data?.items ?? [];

  // Universo base sobre el que se calculan chips y filtros: si solo validadas
  // está activo, los chips también muestran counts de validadas solamente.
  const universo = useMemo(
    () => soloValidadas ? allItems.filter((d) => d.validado) : allItems,
    [allItems, soloValidadas],
  );

  // Chips de categorías derivadas de las asignaciones (dato del backend).
  const catChips = useMemo(() => {
    const counts = new Map<string, number>();
    let sinCat = 0;
    for (const def of universo) {
      const cats = def.categorias ?? [];
      if (cats.length === 0) sinCat++;
      for (const c of cats) counts.set(c.nombre, (counts.get(c.nombre) ?? 0) + 1);
    }
    return {
      categorias: Array.from(counts.entries()).sort((a, b) => b[1] - a[1]),
      sinCat,
    };
  }, [universo]);

  // Aplicar filtros (búsqueda + categoría + solo validadas).
  const items = useMemo(() => {
    const q = search.trim().toLowerCase();
    return universo.filter((def) => {
      if (q && !def.label.toLowerCase().includes(q) && !def.spec_key.toLowerCase().includes(q))
        return false;
      if (catFilter === "__sin__") {
        if ((def.categorias?.length ?? 0) > 0) return false;
      } else if (catFilter) {
        if (!(def.categorias ?? []).some((c) => c.nombre === catFilter)) return false;
      }
      return true;
    });
  }, [universo, search, catFilter]);

  const validadasTotal = allItems.filter((d) => d.validado).length;

  // Agrupar por dominio (primer segmento del spec_key antes del primer "_").
  // Specs sin "_" o con segmento muy genérico van a "General". Esto encaja con
  // la convención de naming <dominio>_<atributo> (camara_montura, lente_apertura,
  // video_out, bateria_capacidad, etc.).
  const DOMAIN_LABELS: Record<string, string> = {
    camara: "Cámara",
    lente: "Lente",
    video: "Video",
    audio: "Audio",
    bateria: "Batería",
    modificador: "Modificador / Iluminación",
    stand: "Stand / Trípode",
    filtro: "Filtro",
    signal: "Routing de señal",
  };
  const grupos = useMemo(() => {
    const map = new Map<string, typeof items>();
    for (const def of items) {
      const firstSeg = def.spec_key.split("_")[0];
      const key = DOMAIN_LABELS[firstSeg] ? firstSeg : "_general";
      const arr = map.get(key) ?? [];
      arr.push(def);
      map.set(key, arr);
    }
    // Orden: dominios conocidos por prioridad declarada, "_general" al final.
    const order = ["camara", "lente", "video", "audio", "signal", "bateria", "modificador", "stand", "filtro", "_general"];
    return order
      .filter((k) => map.has(k))
      .map((k) => ({
        key: k,
        label: k === "_general" ? "General" : DOMAIN_LABELS[k],
        items: (map.get(k) ?? []).slice().sort((a, b) =>
          a.validado === b.validado
            ? a.label.localeCompare(b.label)
            : a.validado ? -1 : 1,
        ),
      }));
  }, [items]);

  const validadasCount = items.filter((d) => d.validado).length;
  const noValidadasCount = items.length - validadasCount;

  return (
    <div className={embedded ? "space-y-6" : "px-4 md:px-6 py-6 space-y-6 max-w-5xl mx-auto"}>
      <header className="flex items-end justify-between gap-3">
        <div>
          {!embedded && (
            <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Back-office › Specs
            </div>
          )}
          <h1 className={embedded
            ? "font-display text-xl text-ink flex items-center gap-2"
            : "font-display text-3xl text-ink flex items-center gap-2"}>
            <Library className={embedded ? "h-5 w-5 text-amber" : "h-6 w-6 text-amber"} />
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

      {!listQ.isLoading && allItems.length === 0 && (
        <div className="rounded-md border hairline border-dashed p-6 text-center text-sm text-muted-foreground">
          No hay definiciones todavía. El seed las crea al iniciar el backend
          desde <code className="font-mono">backend/seeds/spec_templates.py</code>,
          o creá la primera con el botón "Nueva definición".
        </div>
      )}

      {/* Búsqueda + chips filtro categoría */}
      {allItems.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative max-w-md flex-1 min-w-[220px]">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar por label o spec_key…"
                className="pl-7 h-8 text-xs"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-ink"
                  aria-label="Limpiar búsqueda"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
            <button
              type="button"
              onClick={() => setSoloValidadas((v) => !v)}
              className={
                "flex items-center gap-1 rounded-full px-2 py-1 text-[11px] border hairline transition " +
                (soloValidadas
                  ? "bg-emerald-50 border-emerald-300 text-emerald-800"
                  : "bg-background text-muted-foreground hover:text-ink hover:border-ink/30")
              }
              title={
                soloValidadas
                  ? "Mostrar todas (incluye no validadas)"
                  : "Filtrar a las que ya curaste y marcaste con ✓"
              }
            >
              <CheckCircle2 className={"h-3 w-3 " + (soloValidadas ? "text-emerald-600" : "")} />
              Solo validadas ({validadasTotal})
            </button>
          </div>
          <div className="flex flex-wrap gap-1">
            <CategoryChip
              label={`Todas (${universo.length})`}
              active={catFilter === null}
              onClick={() => setCatFilter(null)}
            />
            {catChips.categorias.map(([nombre, count]) => (
              <CategoryChip
                key={nombre}
                label={`${nombre} (${count})`}
                active={catFilter === nombre}
                onClick={() => setCatFilter(catFilter === nombre ? null : nombre)}
              />
            ))}
            {catChips.sinCat > 0 && (
              <CategoryChip
                label={`Sin asignar (${catChips.sinCat})`}
                active={catFilter === "__sin__"}
                onClick={() => setCatFilter(catFilter === "__sin__" ? null : "__sin__")}
              />
            )}
          </div>
        </div>
      )}

      {allItems.length > 0 && items.length === 0 && (
        <div className="rounded-md border hairline border-dashed p-6 text-center text-sm text-muted-foreground">
          Ningún resultado con los filtros actuales.
        </div>
      )}

      {items.length > 0 && (
        <div className="rounded-md border hairline overflow-hidden">
          <div className="grid grid-cols-[24px_1fr_140px_minmax(0,1.2fr)_72px_72px_72px] items-center gap-2 bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            <span aria-hidden />
            <span>Spec key / label</span>
            <span>Tipo</span>
            <span className="hidden md:block">Detalle / Categorías</span>
            <span className="text-right">Usos</span>
            <span className="text-right">Compat</span>
            <span />
          </div>
          <div className="divide-y hairline">
            {items.map((def, idx) => {
              const prev = idx > 0 ? items[idx - 1] : null;
              const showDivider = prev && prev.validado && !def.validado;
              return (
                <div key={def.id}>
                  {showDivider && (
                    <div className="px-3 py-1.5 bg-muted/20 border-y hairline">
                      <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                        Sin validar ({noValidadasCount})
                      </span>
                    </div>
                  )}
                  {idx === 0 && def.validado && (
                    <div className="px-3 py-1.5 bg-emerald-50/40 border-b hairline">
                      <span className="font-mono text-[10px] uppercase tracking-widest text-emerald-800">
                        ✓ Validadas ({validadasCount})
                      </span>
                    </div>
                  )}
                  {idx === 0 && !def.validado && (
                    <div className="px-3 py-1.5 bg-muted/20 border-b hairline">
                      <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                        Sin validar ({noValidadasCount})
                      </span>
                    </div>
                  )}
                  <DefinitionRow
                    def={def}
                    onEdit={() => setEditing(def)}
                    onDelete={() => setConfirmDelete(def)}
                    onToggleCompat={() => toggleCompatMut.mutate(def)}
                    togglingCompat={toggleCompatMut.isPending && toggleCompatMut.variables?.id === def.id}
                    onToggleValidado={() => toggleValidadoMut.mutate(def)}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {editing && (
        <DefinitionFormModal
          key={editing === "new" ? "new" : `def-${editing.id}`}
          definition={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ["admin", "spec-definitions"] });
            // Las asignaciones a categorías afectan a las queries de
            // spec-templates por categoría — invalidamos todas las que
            // empiecen con ese prefix así "Specs por categoría" se entera.
            qc.invalidateQueries({
              predicate: (q) =>
                q.queryKey[0] === "admin" &&
                (q.queryKey[1] === "spec-templates" || q.queryKey[1] === "spec-templates-resumen"),
            });
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

function CategoryChip({
  label, active, onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "rounded-full px-2 py-0.5 text-[10px] border hairline transition " +
        (active
          ? "bg-ink text-background border-ink"
          : "bg-background text-muted-foreground hover:text-ink hover:border-ink/30")
      }
    >
      {label}
    </button>
  );
}

function DefinitionRow({
  def, onEdit, onDelete, onToggleCompat, togglingCompat, onToggleValidado,
}: {
  def: SpecDefinition;
  onEdit: () => void;
  onDelete: () => void;
  onToggleCompat: () => void;
  togglingCompat: boolean;
  onToggleValidado: () => void;
}) {
  return (
    <div className="grid grid-cols-[24px_1fr_140px_minmax(0,1.2fr)_72px_72px_72px] items-center gap-2 px-3 py-2 text-sm hover:bg-muted/20">
      <button
        type="button"
        onClick={onToggleValidado}
        className={
          "rounded-full transition " +
          (def.validado
            ? "text-emerald-600 hover:text-emerald-700"
            : "text-muted-foreground/40 hover:text-muted-foreground")
        }
        title={def.validado ? "Validada — click para desmarcar" : "Marcar como validada"}
        aria-label={def.validado ? "Desmarcar validada" : "Marcar validada"}
      >
        {def.validado ? <CheckCircle2 className="h-4 w-4" /> : <Circle className="h-4 w-4" />}
      </button>
      <div className="min-w-0">
        <div className="font-display text-ink truncate">{def.label}</div>
        <div className="font-mono text-[10px] text-muted-foreground truncate">{def.spec_key}</div>
      </div>
      <div className="text-xs text-muted-foreground">
        {TIPO_LABEL[def.tipo]}
        {def.unidad && <span className="text-muted-foreground/70"> · {def.unidad}</span>}
      </div>
      <div className="hidden md:block text-[10px] text-muted-foreground min-w-0">
        {(def.tipo === "enum" || def.tipo === "multi_enum") && (def.enum_options?.length ?? 0) > 0 && (
          <div className="truncate">{(def.enum_options ?? []).join(", ")}</div>
        )}
        {(def.categorias?.length ?? 0) > 0 ? (
          <div className="flex flex-wrap gap-1 mt-0.5">
            {(def.categorias ?? []).slice(0, 3).map((cat) => (
              <span key={cat.id} className="inline-block rounded bg-muted/60 px-1 py-0.5 text-[9px]">
                {cat.nombre}
              </span>
            ))}
            {(def.categorias?.length ?? 0) > 3 && (
              <span className="text-[9px] text-muted-foreground/60">
                +{(def.categorias?.length ?? 0) - 3}
              </span>
            )}
          </div>
        ) : (
          <div className="text-[9px] italic text-muted-foreground/60">sin asignar</div>
        )}
      </div>
      <div className="text-right text-xs tabular-nums text-muted-foreground">
        {def.uso_categorias ?? 0}c · {def.uso_equipos ?? 0}e
      </div>
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onToggleCompat}
          disabled={togglingCompat}
          title={def.es_compatibilidad ? "Desactivar driver de compatibilidad" : "Activar driver de compatibilidad"}
          className={
            "inline-flex flex-col items-end gap-0.5 rounded-md px-1.5 py-0.5 border hairline transition " +
            (def.es_compatibilidad
              ? "bg-amber-soft/60 border-amber/40 hover:bg-amber-soft"
              : "bg-transparent border-dashed border-muted-foreground/30 text-muted-foreground hover:border-amber/40 hover:text-ink")
          }
        >
          <span className="inline-flex items-center gap-0.5 text-[9px]">
            <Sparkles className={"h-2.5 w-2.5 " + (def.es_compatibilidad ? "text-amber" : "")} />
            compat
          </span>
          {def.es_compatibilidad && (
            <span className="inline-flex items-center gap-0.5 text-[9px] text-muted-foreground">
              {def.compatibilidad_modo === "jerarquia" ? (
                <>
                  <ListOrdered className="h-2.5 w-2.5" /> jerárquica
                </>
              ) : (
                <>
                  <ArrowLeftRight className="h-2.5 w-2.5" /> exacta
                </>
              )}
            </span>
          )}
        </button>
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
    compatibilidad_modo: definition?.compatibilidad_modo ?? "exacta",
  });
  const [enumInput, setEnumInput] = useState((definition?.enum_options ?? []).join(", "));
  const [busy, setBusy] = useState(false);

  // Asignación a categorías: pre-carga las que ya están asignadas, permite
  // marcar/desmarcar. Al guardar, hace el diff y asigna/desasigna lo cambiado.
  const initialCatIds = useMemo(
    () => new Set((definition?.categorias ?? []).map((c) => c.id)),
    [definition?.id],   // eslint-disable-line react-hooks/exhaustive-deps
  );
  const [selectedCatIds, setSelectedCatIds] = useState<Set<number>>(initialCatIds);
  const catsQ = useQuery({
    queryKey: ["admin", "categorias"],
    queryFn: () => adminApi.adminListCategorias(),
    staleTime: 60_000,
  });
  const catsFlat = useMemo(() => {
    const all = catsQ.data ?? [];
    const out: { id: number; path: string; prioridad: number }[] = [];
    const roots = all.filter((c) => c.parent_id == null)
      .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
    for (const root of roots) {
      out.push({ id: root.id, path: root.nombre, prioridad: root.prioridad });
      const hijos = all.filter((c) => c.parent_id === root.id)
        .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
      for (const h of hijos) {
        out.push({ id: h.id, path: `${root.nombre} › ${h.nombre}`, prioridad: h.prioridad });
      }
    }
    return out;
  }, [catsQ.data]);

  function toggleCat(catId: number) {
    setSelectedCatIds((prev) => {
      const next = new Set(prev);
      if (next.has(catId)) next.delete(catId);
      else next.add(catId);
      return next;
    });
  }

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
    const modo: CompatibilidadModo = form.compatibilidad_modo ?? "exacta";
    if (form.es_compatibilidad && modo === "jerarquia" && form.tipo !== "enum") {
      toast.error("Modo jerárquico solo aplica a specs tipo enum (con opciones ordenadas)");
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
        compatibilidad_modo: form.es_compatibilidad ? modo : "exacta",
      };
      let specDefId: number;
      if (isNew) {
        const created = await adminApi.createSpecDefinition(payload);
        specDefId = created.id;
      } else {
        await adminApi.updateSpecDefinition(definition!.id, payload);
        specDefId = definition!.id;
      }

      // Diff de asignaciones a categorías.
      const initialMap = new Map(
        (definition?.categorias ?? []).map((c) => [c.id, c.template_id] as const),
      );
      const initialIds = new Set(initialMap.keys());
      const toAssign: number[] = [];
      const toUnassign: number[] = [];
      for (const id of selectedCatIds) {
        if (!initialIds.has(id)) toAssign.push(id);
      }
      for (const id of initialIds) {
        if (!selectedCatIds.has(id)) {
          const templateId = initialMap.get(id);
          if (templateId != null) toUnassign.push(templateId);
        }
      }
      // Ejecutar en paralelo
      await Promise.all([
        ...toAssign.map((catId) =>
          adminApi.assignSpecToCategoria(catId, { spec_def_id: specDefId }),
        ),
        ...toUnassign.map((templateId) => adminApi.deleteSpecTemplate(templateId)),
      ]);

      const diffMsg =
        toAssign.length || toUnassign.length
          ? ` (+${toAssign.length} / -${toUnassign.length} categorías)`
          : "";
      toast.success(isNew ? `Definición creada${diffMsg}` : `Definición actualizada${diffMsg}`);
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

          <fieldset className="border hairline rounded-md p-2 space-y-1.5">
            <legend className="px-1 text-xs text-muted-foreground">
              Asignar a categorías ({selectedCatIds.size}/{catsFlat.length})
            </legend>
            {catsQ.isLoading && (
              <div className="text-[11px] text-muted-foreground">Cargando categorías…</div>
            )}
            {!catsQ.isLoading && catsFlat.length === 0 && (
              <div className="text-[11px] text-muted-foreground italic">
                No hay categorías creadas todavía.
              </div>
            )}
            {catsFlat.length > 0 && (
              <div className="max-h-56 overflow-y-auto flex flex-col gap-0.5">
                {catsFlat.map((c) => {
                  // Indent por nivel: cuántos "›" hay en el path da la
                  // profundidad. El array ya viene ordenado (root, hijos, root,
                  // hijos, …) así que la jerarquía visual se ve sola.
                  const depth = (c.path.match(/›/g) ?? []).length;
                  // Mostramos solo el último segmento del path (el padre se ve
                  // por contexto/indent). Si es raíz, c.path === último segmento.
                  const lastSegment = c.path.split("›").pop()?.trim() ?? c.path;
                  return (
                    <label
                      key={c.id}
                      className="flex items-center gap-1.5 text-[11px] cursor-pointer hover:bg-muted/30 rounded px-1 py-0.5"
                      style={{ paddingLeft: `${depth * 16 + 4}px` }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedCatIds.has(c.id)}
                        onChange={() => toggleCat(c.id)}
                        className="h-3.5 w-3.5"
                      />
                      {depth > 0 && (
                        <span className="text-muted-foreground/40" aria-hidden>
                          ›
                        </span>
                      )}
                      <span
                        className={
                          "truncate " + (depth === 0 ? "font-medium text-ink" : "")
                        }
                      >
                        {lastSegment}
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
            <p className="text-[10px] text-muted-foreground">
              Cambios se aplican al guardar. Los flags por categoría
              (destacado, prioridad, ayuda override) se editan desde "Specs por categoría".
            </p>
          </fieldset>

          <div className="rounded-md border hairline border-amber/30 bg-amber-soft/30 p-2 space-y-2">
            <label className="flex items-start gap-2 cursor-pointer">
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
                  consideran compatibles. Se usa en
                  GET /equipos/&#123;id&#125;/compatibles.
                </div>
              </div>
            </label>

            {form.es_compatibilidad && (
              <div className="pl-6">
                <Label className="text-xs">Modo de compatibilidad</Label>
                <Select
                  value={form.compatibilidad_modo ?? "exacta"}
                  onValueChange={(v: CompatibilidadModo) =>
                    setForm({ ...form, compatibilidad_modo: v })
                  }
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="exacta">
                      <div className="flex items-center gap-2">
                        <ArrowLeftRight className="h-3.5 w-3.5" />
                        <div className="flex flex-col items-start">
                          <span>Exacta — A = B ⇒ compatible</span>
                          <span className="text-[10px] text-muted-foreground">
                            HDMI/HDMI, Montura E/E, conexión, formato de memoria
                          </span>
                        </div>
                      </div>
                    </SelectItem>
                    <SelectItem value="jerarquia" disabled={form.tipo !== "enum"}>
                      <div className="flex items-center gap-2">
                        <ListOrdered className="h-3.5 w-3.5" />
                        <div className="flex flex-col items-start">
                          <span>Jerárquica — enum ordenado con posiciones</span>
                          <span className="text-[10px] text-muted-foreground">
                            Formato sensor, tamaño área iluminada; requiere tipo enum
                          </span>
                        </div>
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
                {form.compatibilidad_modo === "jerarquia" && (
                  <p className="text-[10px] text-muted-foreground mt-1">
                    Ordená las <strong>opciones</strong> de menor a mayor (ej. MFT,
                    APS-C, S35, Full-frame, Medium Format). En la asignación por
                    categoría definís el <em>rol</em> (contenedor/contenido) para
                    que el algoritmo entienda viñeteo vs crop.
                  </p>
                )}
              </div>
            )}
          </div>

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

