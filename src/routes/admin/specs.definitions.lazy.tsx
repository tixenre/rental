import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Sparkles, Library, AlertCircle, ArrowLeftRight, ListOrdered, CheckCircle2, Circle, Search, X, FolderTree, List } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import {
  adminApi,
  type CompatibilidadModo,
  type SpecDefinition,
  type SpecDefinitionInput,
  type SpecTablaColTipo,
  type SpecTablaColumna,
  type SpecTipo,
  type Unidad,
} from "@/lib/admin/api";
import { useDocumentTitle } from "@/lib/use-document-title";

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
  tabla: "Tabla (columnas configurables)",
};

function SpecDefinitionsPage({ embedded = false }: { embedded?: boolean } = {}) {
  useDocumentTitle("Catálogo global de specs · Back Office");
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

  // ── Tab "Por categoría": agrupar specs por categoría raíz ─────────────
  // Cargar categorías para poder subir por parent_id hasta encontrar root.
  // Una spec asignada a "Cámaras › Cinema" sube a "Cámaras".
  const catsQ = useQuery({
    queryKey: ["admin", "categorias-list"],
    queryFn: () => adminApi.adminListCategorias(),
    staleTime: 60_000,
  });

  const specsByRoot = useMemo(() => {
    const all = catsQ.data ?? [];
    const byId = new Map(all.map((c) => [c.id, c] as const));
    const rootFor = (catId: number): number | null => {
      let cur = byId.get(catId);
      const seen = new Set<number>();
      while (cur && cur.parent_id != null) {
        if (seen.has(cur.id)) return null;  // safety: ciclo defensivo
        seen.add(cur.id);
        cur = byId.get(cur.parent_id);
      }
      return cur?.id ?? null;
    };
    const map = new Map<number, SpecDefinition[]>();
    const sinCat: SpecDefinition[] = [];
    for (const def of items) {
      const cats = def.categorias ?? [];
      if (cats.length === 0) {
        sinCat.push(def);
        continue;
      }
      const rootIds = new Set<number>();
      for (const c of cats) {
        const r = rootFor(c.id);
        if (r != null) rootIds.add(r);
      }
      for (const r of rootIds) {
        const arr = map.get(r) ?? [];
        arr.push(def);
        map.set(r, arr);
      }
    }
    const roots = all
      .filter((c) => c.parent_id == null)
      .sort((a, b) => a.prioridad - b.prioridad || a.nombre.localeCompare(b.nombre));
    const sections = roots
      .map((r) => ({ root: r, specs: (map.get(r.id) ?? []).slice().sort((a, b) => a.label.localeCompare(b.label)) }))
      .filter((s) => s.specs.length > 0);
    return { sections, sinCat };
  }, [items, catsQ.data]);

  // Estado de tab: persistir en localStorage para que la vista preferida
  // del dueño se mantenga entre navegaciones.
  const [activeTab, setActiveTab] = useState<"lista" | "porcat">(() => {
    if (typeof window === "undefined") return "lista";
    return (localStorage.getItem("specs-definitions:view") as "lista" | "porcat") ?? "lista";
  });
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("specs-definitions:view", activeTab);
    }
  }, [activeTab]);

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
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as "lista" | "porcat")}>
          <TabsList className="w-full max-w-sm">
            <TabsTrigger value="lista" className="flex-1 gap-1.5">
              <List className="h-3.5 w-3.5" />
              Lista
            </TabsTrigger>
            <TabsTrigger value="porcat" className="flex-1 gap-1.5">
              <FolderTree className="h-3.5 w-3.5" />
              Por categoría
            </TabsTrigger>
          </TabsList>

          <TabsContent value="lista" className="mt-3">
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
          </TabsContent>

          <TabsContent value="porcat" className="mt-3 space-y-3">
            {catsQ.isLoading && (
              <div className="text-sm text-muted-foreground">Cargando categorías…</div>
            )}
            {!catsQ.isLoading && specsByRoot.sections.length === 0 && specsByRoot.sinCat.length === 0 && (
              <div className="rounded-md border hairline border-dashed p-6 text-center text-sm text-muted-foreground">
                Ningún resultado con los filtros actuales.
              </div>
            )}
            {specsByRoot.sections.map((section) => (
              <RootSection
                key={section.root.id}
                title={section.root.nombre}
                specs={section.specs}
                onEdit={(def) => setEditing(def)}
                onDelete={(def) => setConfirmDelete(def)}
                onToggleCompat={(def) => toggleCompatMut.mutate(def)}
                togglingCompatId={toggleCompatMut.isPending ? (toggleCompatMut.variables?.id ?? null) : null}
                onToggleValidado={(def) => toggleValidadoMut.mutate(def)}
              />
            ))}
            {specsByRoot.sinCat.length > 0 && (
              <RootSection
                key="__sin__"
                title="Sin categoría"
                muted
                specs={specsByRoot.sinCat}
                onEdit={(def) => setEditing(def)}
                onDelete={(def) => setConfirmDelete(def)}
                onToggleCompat={(def) => toggleCompatMut.mutate(def)}
                togglingCompatId={toggleCompatMut.isPending ? (toggleCompatMut.variables?.id ?? null) : null}
                onToggleValidado={(def) => toggleValidadoMut.mutate(def)}
              />
            )}
          </TabsContent>
        </Tabs>
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

// ── Sección de specs agrupadas por categoría raíz ──────────────────────

function RootSection({
  title, specs, onEdit, onDelete, onToggleCompat, togglingCompatId,
  onToggleValidado, muted,
}: {
  title: string;
  specs: SpecDefinition[];
  onEdit: (def: SpecDefinition) => void;
  onDelete: (def: SpecDefinition) => void;
  onToggleCompat: (def: SpecDefinition) => void;
  togglingCompatId: number | null;
  onToggleValidado: (def: SpecDefinition) => void;
  muted?: boolean;
}) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-md border hairline overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={
          "w-full flex items-center justify-between px-3 py-2 text-left transition " +
          (muted
            ? "bg-muted/20 hover:bg-muted/40"
            : "bg-amber-soft/30 hover:bg-amber-soft/50")
        }
      >
        <div className="flex items-center gap-2">
          <FolderTree className={"h-3.5 w-3.5 " + (muted ? "text-muted-foreground" : "text-amber")} />
          <span className={"font-display text-sm " + (muted ? "text-muted-foreground" : "text-ink")}>
            {title}
          </span>
          <Badge variant="outline" className="text-[10px] h-5">
            {specs.length}
          </Badge>
        </div>
        <span className="text-[10px] text-muted-foreground font-mono">
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open && (
        <div className="divide-y hairline">
          {specs.map((def) => (
            <DefinitionRow
              key={def.id}
              def={def}
              onEdit={() => onEdit(def)}
              onDelete={() => onDelete(def)}
              onToggleCompat={() => onToggleCompat(def)}
              togglingCompat={togglingCompatId === def.id}
              onToggleValidado={() => onToggleValidado(def)}
            />
          ))}
        </div>
      )}
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
    tabla_columnas: definition?.tabla_columnas ?? [],
    output_config: definition?.output_config ?? null,
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
    if (form.tipo === "tabla") {
      const cols = form.tabla_columnas ?? [];
      if (cols.length === 0) {
        toast.error("Para tipo tabla tenés que definir al menos una columna");
        return;
      }
      const keys = new Set<string>();
      for (const c of cols) {
        const k = c.key?.trim();
        if (!k || !c.label?.trim() || !c.tipo) {
          toast.error("Cada columna necesita key, label y tipo");
          return;
        }
        if (keys.has(k)) {
          toast.error(`Columna key '${k}' duplicada`);
          return;
        }
        keys.add(k);
        if (c.tipo === "enum" && (!c.options || c.options.length === 0)) {
          toast.error(`Columna '${k}' enum: hay que listar opciones`);
          return;
        }
      }
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
        tabla_columnas: form.tipo === "tabla" ? (form.tabla_columnas ?? []) : null,
        output_config: form.tipo === "tabla" ? (form.output_config ?? null) : null,
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
        className="w-full max-w-xl max-h-[90vh] rounded-lg bg-background border hairline shadow-lg flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="border-b hairline px-4 py-3 shrink-0">
          <div className="font-display text-base text-ink">
            {isNew ? "Nueva definición" : "Editar definición"}
          </div>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Cambios afectan a todas las categorías que usan esta spec.
          </p>
        </header>

        <div className="p-4 space-y-3 overflow-y-auto">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Spec key (interno)</Label>
              <Input
                value={form.spec_key}
                onChange={(e) => setForm({ ...form, spec_key: e.target.value })}
                placeholder="ej. montura"
                className="font-mono"
              />
              <p className="text-[10px] text-muted-foreground mt-1">
                Solo a-z 0-9 _. Editable durante construcción.
              </p>
              {!isNew && definition && form.spec_key.trim() !== definition.spec_key && (
                <p className="text-[10px] text-amber-700 mt-1 flex items-start gap-1">
                  <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                  <span>
                    Estás renombrando <code className="font-mono">{definition.spec_key}</code> →{" "}
                    <code className="font-mono">{form.spec_key.trim()}</code>. Verificá que no haya
                    queries hardcoded en seeds/scripts que usen el nombre viejo.
                  </span>
                </p>
              )}
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
                {(["string", "number", "rango", "wxh", "wxhxd", "enum", "multi_enum", "bool", "tabla"] as SpecTipo[]).map((t) => (
                  <SelectItem key={t} value={t}>{TIPO_LABEL[t]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {form.tipo === "tabla" && (
            <>
              <TablaColumnasEditor
                columnas={form.tabla_columnas ?? []}
                onChange={(cols) => setForm({ ...form, tabla_columnas: cols })}
              />
              <div>
                <Label className="text-xs">
                  Estrategia de filas en placeholder
                </Label>
                <Select
                  value={form.output_config?.row_strategy ?? "all"}
                  onValueChange={(v: "all" | "first" | "last") =>
                    setForm({
                      ...form,
                      output_config: v === "all" ? null : { row_strategy: v },
                    })
                  }
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todas las filas (default)</SelectItem>
                    <SelectItem value="first">Solo primera fila</SelectItem>
                    <SelectItem value="last">Solo última fila</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-[10px] text-muted-foreground mt-1">
                  Qué filas se rinden cuando aparece <code className="font-mono">{"{spec:Label}"}</code> en
                  el nombre público (sin selector de columna). "Primera" / "última" sirven cuando el nombre
                  es single-line y solo querés mostrar una fila representativa.
                </p>
              </div>
            </>
          )}

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

        <footer className="border-t hairline px-4 py-3 flex justify-end gap-2 shrink-0">
          <Button variant="outline" onClick={onClose} disabled={busy}>Cancelar</Button>
          <Button onClick={handleSave} disabled={busy}>
            {busy ? "Guardando…" : isNew ? "Crear" : "Guardar"}
          </Button>
        </footer>
      </div>
    </div>
  );
}

// ── Picker de unidades del catálogo global ──────────────────────────────

function UnidadesPicker({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const unidadesQ = useQuery({
    queryKey: ["admin", "unidades"],
    queryFn: () => adminApi.listUnidades(),
    staleTime: 60_000,
  });
  const unidades: Unidad[] = unidadesQ.data?.items ?? [];
  const selectedSet = new Set(selected);

  // Agrupar por dimensión para que el dueño encuentre rápido.
  const grupos = useMemo(() => {
    const map = new Map<string, Unidad[]>();
    for (const u of unidades) {
      const d = u.dimension?.trim() || "_otras";
      const arr = map.get(d) ?? [];
      arr.push(u);
      map.set(d, arr);
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => {
        if (a === "_otras") return 1;
        if (b === "_otras") return -1;
        return a.localeCompare(b);
      })
      .map(([dim, us]) => ({
        dimension: dim === "_otras" ? "Otras" : dim,
        unidades: us.slice().sort((a, b) => a.simbolo.localeCompare(b.simbolo)),
      }));
  }, [unidades]);

  function toggle(simbolo: string) {
    if (selectedSet.has(simbolo)) {
      onChange(selected.filter((s) => s !== simbolo));
    } else {
      onChange([...selected, simbolo]);
    }
  }

  if (unidadesQ.isLoading) {
    return <div className="text-[10px] text-muted-foreground italic">Cargando unidades…</div>;
  }
  if (unidades.length === 0) {
    return (
      <div className="text-[10px] text-muted-foreground italic">
        No hay unidades en el catálogo.{" "}
        <a href="/admin/unidades" className="underline hover:text-ink" target="_blank" rel="noreferrer">
          Crear unidades →
        </a>
      </div>
    );
  }
  return (
    <div className="space-y-1">
      <div className="text-[10px] text-muted-foreground">
        Unidades permitidas (click para seleccionar):{" "}
        <span className="text-ink/70">{selected.length} de {unidades.length}</span>
      </div>
      <div className="max-h-32 overflow-y-auto border hairline rounded p-1 space-y-1 bg-background">
        {grupos.map((g) => (
          <div key={g.dimension}>
            <div className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60 px-1 pt-0.5">
              {g.dimension}
            </div>
            <div className="flex flex-wrap gap-0.5">
              {g.unidades.map((u) => {
                const isOn = selectedSet.has(u.simbolo);
                return (
                  <button
                    key={u.id}
                    type="button"
                    onClick={() => toggle(u.simbolo)}
                    className={
                      "rounded-full px-1.5 py-0.5 text-[10px] border hairline transition " +
                      (isOn
                        ? "bg-amber-soft border-amber/40 text-ink"
                        : "bg-background text-muted-foreground hover:text-ink hover:border-ink/30")
                    }
                    title={`${u.nombre} (${u.simbolo})`}
                  >
                    {u.simbolo}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}


// ── Editor de columnas para spec tipo `tabla` ───────────────────────────

const COL_TIPO_LABEL: Record<SpecTablaColTipo, string> = {
  number: "Número",
  valor_unidad: "Núm + Unidad",
  string: "Texto",
  enum: "Opciones",
  bool: "Sí/No",
};

/** Slugifica un label a una key válida (a-z0-9_): lowercase, sin tildes,
 *  espacios → "_". Si el resultado no empieza con letra, prepende "c_". */
function slugifyKey(label: string): string {
  const base = label
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  if (!base) return "";
  return /^[a-z]/.test(base) ? base : `c_${base}`;
}

function TablaColumnasEditor({
  columnas,
  onChange,
}: {
  columnas: SpecTablaColumna[];
  onChange: (cols: SpecTablaColumna[]) => void;
}) {
  // Tracking de qué columnas tienen key manual (override del autogen).
  // Por default todas autogeneran. Si el dueño edita la key a mano, queda
  // fijada (no la pisamos al cambiar label).
  const [manualKey, setManualKey] = useState<Set<number>>(new Set());
  const [showAdvanced, setShowAdvanced] = useState<Set<number>>(new Set());

  function update(idx: number, patch: Partial<SpecTablaColumna>) {
    onChange(columnas.map((c, i) => (i === idx ? { ...c, ...patch } : c)));
  }
  function updateLabel(idx: number, label: string) {
    const next: Partial<SpecTablaColumna> = { label };
    if (!manualKey.has(idx)) next.key = slugifyKey(label);
    update(idx, next);
  }
  function setKeyManual(idx: number, key: string) {
    setManualKey((s) => new Set(s).add(idx));
    update(idx, { key });
  }
  function toggleAdvanced(idx: number) {
    setShowAdvanced((s) => {
      const next = new Set(s);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }
  function addCol() {
    onChange([...columnas, { key: "", label: "", tipo: "number" }]);
  }
  function removeCol(idx: number) {
    onChange(columnas.filter((_, i) => i !== idx));
  }

  return (
    <fieldset className="border hairline rounded-md p-2 space-y-2">
      <legend className="px-1 text-xs text-muted-foreground">
        Columnas de la tabla
      </legend>
      <p className="text-[10px] text-muted-foreground -mt-1">
        Cada columna tiene un nombre y (opcional) una unidad. Al cargar un equipo
        agregás filas con un valor por columna.
      </p>
      {columnas.length === 0 && (
        <div className="text-[11px] text-muted-foreground italic py-1">
          Sin columnas. Agregá al menos una.
        </div>
      )}
      {columnas.length > 0 && (
        <div className="flex items-stretch gap-1 overflow-x-auto pb-1">
          {columnas.map((c, idx) => (
            <Fragment key={idx}>
              {idx > 0 && (
                <Input
                  value={c.prefijo ?? ""}
                  onChange={(e) => update(idx, { prefijo: e.target.value || null })}
                  placeholder="conector"
                  className="h-auto self-center w-16 text-xs italic text-center px-1 border-dashed"
                  title='Texto fijo entre columnas. Ej. "a" → "10000 lm a 5700 K"'
                />
              )}
              <div className="border hairline rounded p-2 bg-muted/20 min-w-[180px] flex-1 space-y-1">
                <div className="flex items-start justify-between gap-1">
                  <Input
                    value={c.label}
                    onChange={(e) => updateLabel(idx, e.target.value)}
                    placeholder="Nombre"
                    className="h-7 text-xs font-medium border-0 bg-transparent shadow-none focus-visible:ring-1 px-1"
                  />
                  <button
                    type="button"
                    onClick={() => removeCol(idx)}
                    className="h-6 w-6 shrink-0 inline-flex items-center justify-center text-muted-foreground/60 hover:text-destructive rounded"
                    title="Borrar columna"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
                <div className="flex items-center gap-1">
                  {c.tipo !== "valor_unidad" && (
                    <Input
                      value={c.unidad ?? ""}
                      onChange={(e) => update(idx, { unidad: e.target.value || null })}
                      placeholder="unidad fija"
                      className="h-6 text-[11px] flex-1 px-1.5"
                    />
                  )}
                  {c.tipo === "valor_unidad" && (
                    <div className="flex-1 text-[10px] text-muted-foreground italic px-1">
                      número + unidad por fila
                    </div>
                  )}
                  <Select
                    value={c.tipo}
                    onValueChange={(v: SpecTablaColTipo) => update(idx, { tipo: v })}
                  >
                    <SelectTrigger className="h-6 text-[11px] w-[120px] px-1.5"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {(["valor_unidad", "number", "string", "enum", "bool"] as SpecTablaColTipo[]).map((t) => (
                        <SelectItem key={t} value={t} className="text-xs">{COL_TIPO_LABEL[t]}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {c.tipo === "enum" && (
                  <Input
                    value={(c.options ?? []).join(", ")}
                    onChange={(e) =>
                      update(idx, {
                        options: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                      })
                    }
                    placeholder="opciones: 2700K, 3200K…"
                    className="h-6 text-[11px] px-1.5"
                  />
                )}
                {c.tipo === "valor_unidad" && (
                  <UnidadesPicker
                    selected={c.unidades_opciones ?? []}
                    onChange={(opts) => update(idx, { unidades_opciones: opts })}
                  />
                )}
                <button
                  type="button"
                  onClick={() => toggleAdvanced(idx)}
                  className="text-[9px] text-muted-foreground hover:text-ink font-mono w-full text-left px-1"
                >
                  {showAdvanced.has(idx) ? "▾" : "▸"} key: <span className="text-ink/70">{c.key || "(auto)"}</span>
                </button>
                {showAdvanced.has(idx) && (
                  <Input
                    value={c.key}
                    onChange={(e) => setKeyManual(idx, e.target.value)}
                    placeholder="key custom"
                    className="font-mono h-6 text-[11px] px-1.5"
                  />
                )}
              </div>
            </Fragment>
          ))}
          <button
            type="button"
            onClick={addCol}
            className="border hairline border-dashed rounded px-2 min-w-[80px] flex items-center justify-center gap-1 text-xs text-muted-foreground hover:text-ink hover:border-ink/30 transition"
            title="Agregar columna"
          >
            <Plus className="h-3 w-3" /> col
          </button>
        </div>
      )}
      {columnas.length === 0 && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addCol}
          className="h-7 text-xs gap-1"
        >
          <Plus className="h-3 w-3" /> Agregar columna
        </Button>
      )}
    </fieldset>
  );
}

