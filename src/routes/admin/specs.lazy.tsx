/**
 * specs.lazy.tsx — UI consolidada de specs por categoría raíz.
 *
 * Reemplaza varias UIs viejas (specs.definitions, specs.observatorio,
 * specs.familias, gear-compatibility, etc.). Lo importante:
 * - Tabs por categoría raíz (Cámaras, Lentes, …).
 * - Lista con drag-and-drop para reordenar prioridad.
 * - Por spec, 3 switches inline: Favorito / En Nombre / En Filtros.
 * - Drawer al click con detalle completo (tipo, valores, ayuda, uso).
 */
import { createLazyFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
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
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Star, FileText, Filter, Info, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useDocumentTitle } from "@/lib/use-document-title";
import { authedJson } from "@/lib/authedFetch";

export const Route = createLazyFileRoute("/admin/specs")({
  component: SpecsConsolidadasPage,
});

type SpecTipo = "string" | "number" | "enum" | "multi_enum" | "bool" | "rango" | "wxh" | "wxhxd" | "tabla";

interface Spec {
  id: number;
  spec_key: string;
  label: string;
  tipo: SpecTipo;
  unidad: string | null;
  enum_options: string[] | null;
  ayuda: string | null;
  output_config: { name_format?: string; row_strategy?: string } | null;
  es_compatibilidad: boolean;
  compatibilidad_modo: string | null;
  favorito: boolean;
  en_nombre: boolean;
  en_filtros: boolean;
  prioridad: number;
  uso_equipos: number;
}

interface CategoriaConSpecs {
  id: number;
  nombre: string;
  prioridad: number | null;
  grupo_visual: string | null;
  nombre_publico_template: string | null;
  specs: Spec[];
}

interface PorCategoriaResponse {
  categorias: CategoriaConSpecs[];
}

function SpecsConsolidadasPage() {
  useDocumentTitle("Specs · Back Office");
  const q = useQuery<PorCategoriaResponse>({
    queryKey: ["admin", "specs-por-categoria"],
    queryFn: () => authedJson<PorCategoriaResponse>("/api/admin/specs/por-categoria"),
  });

  const [selectedSpec, setSelectedSpec] = useState<Spec | null>(null);
  const [activeTab, setActiveTab] = useState<string>("");

  // Set default tab when data arrives
  const categorias = q.data?.categorias ?? [];
  const defaultTab = categorias[0]?.id ? String(categorias[0].id) : "";
  const currentTab = activeTab || defaultTab;

  return (
    <div className="px-4 md:px-6 py-6 space-y-6 max-w-6xl mx-auto">
      <header>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
          Back-office · Inventario
        </div>
        <h1 className="font-display text-3xl text-ink">Specs</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Definiciones de specs por categoría raíz. Marcá favoritos para que aparezcan en card,
          mini-ficha, lateral y pills de la ficha. Arrastrá para reordenar.
        </p>
      </header>

      {q.isLoading && (
        <div className="text-sm text-muted-foreground">Cargando specs…</div>
      )}
      {q.isError && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 space-y-2">
          <div className="text-sm font-medium text-destructive">Error cargando specs.</div>
          <div className="text-xs text-destructive/80 font-mono break-all">
            {(q.error as Error)?.message ?? "Error desconocido"}
          </div>
          <div className="text-xs text-muted-foreground">
            Si el deploy es reciente, esperá un minuto y refrescá. Si persiste, revisá que la migración
            <code className="mx-1 bg-muted px-1 rounded">e5a7b9d2c4f1_spec_def_flags</code>
            haya corrido en producción.
          </div>
        </div>
      )}

      {!q.isLoading && !q.isError && categorias.length === 0 && (
        <div className="text-sm text-muted-foreground border rounded-lg p-6 text-center">
          No hay specs sembradas todavía.
        </div>
      )}

      {categorias.length > 0 && (
        <Tabs value={currentTab} onValueChange={setActiveTab}>
          <TabsList className="flex flex-wrap h-auto gap-1">
            {categorias.map((cat) => (
              <TabsTrigger key={cat.id} value={String(cat.id)} className="gap-2">
                {cat.nombre}
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                  {cat.specs.length}
                </Badge>
              </TabsTrigger>
            ))}
          </TabsList>
          {categorias.map((cat) => (
            <TabsContent key={cat.id} value={String(cat.id)} className="mt-4">
              <CategoriaPanel
                categoria={cat}
                onSelectSpec={(s) => setSelectedSpec(s)}
              />
            </TabsContent>
          ))}
        </Tabs>
      )}

      {selectedSpec && (
        <SpecDetailDrawer
          spec={selectedSpec}
          onClose={() => setSelectedSpec(null)}
        />
      )}
    </div>
  );
}

function CategoriaPanel({
  categoria,
  onSelectSpec,
}: {
  categoria: CategoriaConSpecs;
  onSelectSpec: (s: Spec) => void;
}) {
  const queryClient = useQueryClient();
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  // Sort specs by prioridad asc (lower = first)
  const sortedSpecs = useMemo(
    () => [...categoria.specs].sort((a, b) => a.prioridad - b.prioridad),
    [categoria.specs],
  );

  const reorderMutation = useMutation({
    mutationFn: (specIds: number[]) =>
      authedJson<{ ok: true }>(`/api/admin/specs/categoria/${categoria.id}/reorder`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spec_ids: specIds }),
      }),
    onSuccess: () => {
      toast.success("Orden actualizado");
      queryClient.invalidateQueries({ queryKey: ["admin", "specs-por-categoria"] });
    },
    onError: () => toast.error("Error guardando el orden"),
  });

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = sortedSpecs.findIndex((s) => s.id === active.id);
    const newIndex = sortedSpecs.findIndex((s) => s.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = arrayMove(sortedSpecs, oldIndex, newIndex);
    reorderMutation.mutate(reordered.map((s) => s.id));
  };

  // Stats
  const favoritos = sortedSpecs.filter((s) => s.favorito).length;
  const enNombre = sortedSpecs.filter((s) => s.en_nombre).length;
  const enFiltros = sortedSpecs.filter((s) => s.en_filtros).length;

  return (
    <div className="space-y-4">
      {/* Stats bar */}
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="outline" className="gap-1.5">
          <Star className="h-3 w-3" /> {favoritos} favoritos
        </Badge>
        <Badge variant="outline" className="gap-1.5">
          <FileText className="h-3 w-3" /> {enNombre} en nombre
        </Badge>
        <Badge variant="outline" className="gap-1.5">
          <Filter className="h-3 w-3" /> {enFiltros} en filtros
        </Badge>
        {categoria.grupo_visual && (
          <span className="ml-auto">
            Bloque visual: <span className="text-ink">{categoria.grupo_visual}</span>
          </span>
        )}
      </div>

      {/* Editor del template del nombre auto-generado */}
      <NombreTemplateEditor
        categoriaId={categoria.id}
        categoriaNombre={categoria.nombre}
        currentTemplate={categoria.nombre_publico_template}
        specsEnNombre={sortedSpecs.filter((s) => s.en_nombre)}
      />

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={sortedSpecs.map((s) => s.id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-1">
            {sortedSpecs.map((spec) => (
              <SortableSpecRow
                key={spec.id}
                spec={spec}
                onSelect={() => onSelectSpec(spec)}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
}

function SortableSpecRow({ spec, onSelect }: { spec: Spec; onSelect: () => void }) {
  const queryClient = useQueryClient();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: spec.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const patchFlags = useMutation({
    mutationFn: (changes: Partial<Pick<Spec, "favorito" | "en_nombre" | "en_filtros">>) =>
      authedJson<{ ok: true }>(`/api/admin/spec-definitions/${spec.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changes),
      }),
    onMutate: async (changes) => {
      await queryClient.cancelQueries({ queryKey: ["admin", "specs-por-categoria"] });
      const previous = queryClient.getQueryData<PorCategoriaResponse>([
        "admin",
        "specs-por-categoria",
      ]);
      queryClient.setQueryData<PorCategoriaResponse>(
        ["admin", "specs-por-categoria"],
        (old) => {
          if (!old) return old;
          return {
            categorias: old.categorias.map((cat) => ({
              ...cat,
              specs: cat.specs.map((s) =>
                s.id === spec.id ? { ...s, ...changes } : s,
              ),
            })),
          };
        },
      );
      return { previous };
    },
    onError: (_err, _changes, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["admin", "specs-por-categoria"], context.previous);
      }
      toast.error("Error guardando flag");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "specs-por-categoria"] });
    },
  });

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 rounded-lg border bg-card px-2 py-2 hover:border-ink/40 transition-colors"
    >
      <button
        type="button"
        className="touch-none cursor-grab active:cursor-grabbing text-muted-foreground hover:text-ink"
        {...attributes}
        {...listeners}
        aria-label="Arrastrar"
      >
        <GripVertical className="h-4 w-4" />
      </button>

      <div
        className="flex-1 min-w-0 cursor-pointer"
        onClick={onSelect}
      >
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-medium text-ink truncate">{spec.label}</span>
          <Badge variant="outline" className="text-[10px] font-mono px-1 py-0">
            {spec.tipo}
          </Badge>
          {spec.unidad && (
            <span className="text-[10px] text-muted-foreground font-mono">{spec.unidad}</span>
          )}
          {spec.es_compatibilidad && (
            <Badge className="text-[10px] px-1 py-0 bg-amber/20 text-amber-foreground border-amber/40">
              compat
            </Badge>
          )}
        </div>
        <div className="text-[11px] text-muted-foreground font-mono mt-0.5">
          {spec.spec_key}
          <span className="ml-2">· {spec.uso_equipos} equipos</span>
        </div>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <FlagSwitch
          label="Fav"
          icon={<Star className="h-3 w-3" />}
          checked={spec.favorito}
          onChange={(v) => patchFlags.mutate({ favorito: v })}
        />
        <FlagSwitch
          label="Nombre"
          icon={<FileText className="h-3 w-3" />}
          checked={spec.en_nombre}
          onChange={(v) => patchFlags.mutate({ en_nombre: v })}
        />
        <FlagSwitch
          label="Filtros"
          icon={<Filter className="h-3 w-3" />}
          checked={spec.en_filtros}
          onChange={(v) => patchFlags.mutate({ en_filtros: v })}
        />
      </div>
    </div>
  );
}

function FlagSwitch({
  label,
  icon,
  checked,
  onChange,
}: {
  label: string;
  icon: React.ReactNode;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-1.5 cursor-pointer select-none">
      <span className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
        {icon}
        <span className="hidden sm:inline">{label}</span>
      </span>
      <Switch checked={checked} onCheckedChange={onChange} />
    </label>
  );
}

function SpecDetailDrawer({ spec, onClose }: { spec: Spec; onClose: () => void }) {
  // Reactivo: si la query refresca (por ej. después de toggle un flag),
  // el drawer se re-renderiza con el dato fresco automáticamente.
  const { data: fresh = spec } = useQuery({
    queryKey: ["admin", "specs-por-categoria"],
    queryFn: () => authedJson<PorCategoriaResponse>("/api/admin/specs/por-categoria"),
    select: (data) =>
      data.categorias.flatMap((c) => c.specs).find((s) => s.id === spec.id) ?? spec,
  });

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex justify-end"
      onClick={onClose}
    >
      <div
        className="bg-background w-full max-w-md h-full overflow-y-auto p-6 shadow-2xl border-l"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              spec_key
            </div>
            <div className="font-mono text-sm text-ink">{fresh.spec_key}</div>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} className="-mt-2 -mr-2">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <h2 className="font-display text-2xl text-ink">{fresh.label}</h2>

        <div className="mt-6 space-y-4 text-sm">
          <DetailRow label="Tipo">
            <Badge variant="outline" className="font-mono">{fresh.tipo}</Badge>
            {fresh.unidad && (
              <span className="text-muted-foreground ml-2">unidad: <code>{fresh.unidad}</code></span>
            )}
          </DetailRow>

          {(fresh.tipo === "enum" || fresh.tipo === "multi_enum") && (
            <DetailRow label={`Valores posibles${fresh.tipo === "multi_enum" ? " (multi-selección)" : ""}`}>
              {fresh.enum_options && fresh.enum_options.length > 0 ? (
                <ul className="space-y-1 mt-1">
                  {fresh.enum_options.map((opt) => (
                    <li key={opt} className="text-sm">
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{opt}</code>
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="text-muted-foreground italic text-xs">Sin opciones definidas</span>
              )}
            </DetailRow>
          )}

          {fresh.tipo === "bool" && (
            <DetailRow label="Valores posibles">
              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">Sí / No</code>
            </DetailRow>
          )}

          {fresh.tipo === "number" && (
            <DetailRow label="Valores posibles">
              <span className="text-xs text-muted-foreground">
                Número{fresh.unidad ? ` en ${fresh.unidad}` : ""}
              </span>
            </DetailRow>
          )}

          {fresh.tipo === "rango" && (
            <DetailRow label="Valores posibles">
              <span className="text-xs text-muted-foreground">
                Rango{fresh.unidad ? ` en ${fresh.unidad}` : ""}. Ej: [80, 102400] o [4]
              </span>
            </DetailRow>
          )}

          {fresh.tipo === "string" && (
            <DetailRow label="Valores posibles">
              <span className="text-xs text-muted-foreground">Texto libre</span>
            </DetailRow>
          )}

          <DetailRow label="Prioridad">
            <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{fresh.prioridad}</code>
            <span className="text-xs text-muted-foreground ml-2">
              (orden con drag-and-drop)
            </span>
          </DetailRow>

          {fresh.ayuda && (
            <DetailRow label="Ayuda">
              <p className="text-xs text-muted-foreground italic mt-0.5">{fresh.ayuda}</p>
            </DetailRow>
          )}

          <DetailRow label="Uso">
            <span>{fresh.uso_equipos} equipos lo tienen cargado</span>
          </DetailRow>

          <div className="border-t pt-4 mt-6 space-y-3">
            <h3 className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              Flags
            </h3>
            <FlagDisplay
              icon={<Star className="h-3 w-3" />}
              label="Favorito"
              checked={fresh.favorito}
              description="Aparece en card, mini-ficha, lateral y pills sobre la descripción."
            />
            <FlagDisplay
              icon={<FileText className="h-3 w-3" />}
              label="En Nombre"
              checked={fresh.en_nombre}
              description="Se incluye en el título auto-generado del equipo."
            />
            <FlagDisplay
              icon={<Filter className="h-3 w-3" />}
              label="En Filtros"
              checked={fresh.en_filtros}
              description="Aparece en el sidebar de filtros del catálogo."
            />
          </div>

          {/* Formato en título auto. Solo útil si está marcado "En Nombre". */}
          {fresh.en_nombre && (
            <div className="border-t pt-4">
              <NameFormatEditor spec={fresh} />
            </div>
          )}

          {fresh.es_compatibilidad && (
            <div className="border-t pt-4 space-y-2">
              <h3 className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Info className="h-3 w-3" />
                Motor de compatibilidad
              </h3>
              <div className="text-xs">
                Modo: <code className="bg-muted px-1.5 py-0.5 rounded">{fresh.compatibilidad_modo}</code>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="mt-0.5">{children}</div>
    </div>
  );
}

function FlagDisplay({
  icon,
  label,
  checked,
  description,
}: {
  icon: React.ReactNode;
  label: string;
  checked: boolean;
  description: string;
}) {
  return (
    <div className="flex items-start gap-2.5">
      <div className={`mt-1 ${checked ? "text-amber" : "text-muted-foreground/40"}`}>
        {icon}
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-ink">{label}</span>
          {checked ? (
            <Badge className="text-[10px] px-1.5 py-0 bg-amber/20 text-amber-foreground border-amber/40">
              ON
            </Badge>
          ) : (
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">OFF</Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
      </div>
    </div>
  );
}

/**
 * Editor del template del nombre auto-generado para la categoría.
 *
 * El template usa placeholders como `{spec:Label}` que se reemplazan por el
 * valor del spec del equipo cuando se genera el nombre público. Por ejemplo:
 *   "{Marca} {Modelo} {spec:Resolución máxima} {spec:Lens mount}"
 *   → "Sony FX3A 4K E-mount"
 *
 * El editor sólo permite insertar placeholders de specs marcados como
 * "en_nombre". Para activar más specs, el admin las marca abajo.
 */
function NombreTemplateEditor({
  categoriaId,
  categoriaNombre,
  currentTemplate,
  specsEnNombre,
}: {
  categoriaId: number;
  categoriaNombre: string;
  currentTemplate: string | null;
  specsEnNombre: Spec[];
}) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState<string>(currentTemplate ?? "");
  const [isDirty, setIsDirty] = useState(false);

  // Sync cuando cambie el template desde el servidor (otra pestaña, etc.)
  // pero solo si no estamos editando.
  useMemo(() => {
    if (!isDirty) setValue(currentTemplate ?? "");
  }, [currentTemplate, isDirty]);

  const saveMutation = useMutation({
    mutationFn: (template: string) =>
      authedJson<{ ok: true; nombres_regenerados?: number }>(
        `/api/admin/categorias/${categoriaId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nombre_publico_template: template.trim() || null }),
        },
      ),
    onSuccess: (data) => {
      const n = data.nombres_regenerados ?? 0;
      toast.success(
        n > 0
          ? `Template guardado · ${n} ${n === 1 ? "equipo" : "equipos"} con nombre regenerado`
          : `Template de ${categoriaNombre} guardado`,
      );
      setIsDirty(false);
      queryClient.invalidateQueries({ queryKey: ["admin", "specs-por-categoria"] });
    },
    onError: () => toast.error("Error guardando el template"),
  });

  const insertPlaceholder = (label: string) => {
    setValue((v) => `${v}${v && !v.endsWith(" ") ? " " : ""}{spec:${label}}`);
    setIsDirty(true);
  };

  return (
    <details
      open={!!currentTemplate || isDirty}
      className="rounded-lg border bg-card overflow-hidden"
    >
      <summary className="px-4 py-3 cursor-pointer flex items-center gap-2 hover:bg-muted/50 transition-colors">
        <FileText className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium text-ink">
          Plantilla del nombre auto-generado
        </span>
        {currentTemplate && (
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
            configurado
          </Badge>
        )}
        <span className="ml-auto text-xs text-muted-foreground">
          {specsEnNombre.length} specs disponibles
        </span>
      </summary>

      <div className="px-4 py-4 border-t space-y-3">
        <div className="text-xs text-muted-foreground">
          Usá placeholders <code className="bg-muted px-1 rounded font-mono">{`{spec:Label}`}</code> para insertar valores
          de specs. Los placeholders <code className="bg-muted px-1 rounded font-mono">{`{Marca}`}</code>,
          <code className="bg-muted px-1 rounded font-mono mx-1">{`{Modelo}`}</code>
          y <code className="bg-muted px-1 rounded font-mono">{`{Nombre}`}</code> también funcionan.
        </div>

        <input
          type="text"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setIsDirty(true);
          }}
          placeholder={`Ej: {Marca} {Modelo} {spec:${specsEnNombre[0]?.label ?? "Lens mount"}}`}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
        />

        {specsEnNombre.length > 0 && (
          <div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">
              Insertar spec (click)
            </div>
            <div className="flex flex-wrap gap-1.5">
              {specsEnNombre.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => insertPlaceholder(s.label)}
                  className="rounded-full border bg-background px-2 py-0.5 text-xs hover:border-ink hover:bg-muted transition"
                >
                  + {s.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {specsEnNombre.length === 0 && (
          <div className="text-xs text-muted-foreground italic">
            Marcá specs con "Nombre" debajo para que aparezcan acá como insertables.
          </div>
        )}

        <div className="flex items-center gap-2 pt-1">
          <Button
            size="sm"
            disabled={!isDirty || saveMutation.isPending}
            onClick={() => saveMutation.mutate(value)}
          >
            {saveMutation.isPending ? "Guardando…" : "Guardar template"}
          </Button>
          {isDirty && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setValue(currentTemplate ?? "");
                setIsDirty(false);
              }}
            >
              Descartar cambios
            </Button>
          )}
        </div>
      </div>
    </details>
  );
}

/**
 * Editor del formato del spec dentro del nombre auto-generado.
 *
 * Sin formato, el placeholder {spec:Label} en el template del nombre se
 * renderiza solo con el value (ej. "19389"). Con formato custom, podés
 * decir "Potencia {value} lúmenes" para que se renderice como
 * "Potencia 19389 lúmenes" automáticamente en cada equipo.
 *
 * Placeholders disponibles: {value}, {unidad}.
 */
function NameFormatEditor({ spec }: { spec: Spec }) {
  const queryClient = useQueryClient();
  const current = spec.output_config?.name_format ?? "";
  const [value, setValue] = useState<string>(current);
  const [isDirty, setIsDirty] = useState(false);

  useMemo(() => {
    if (!isDirty) setValue(current);
  }, [current, isDirty]);

  const saveMutation = useMutation({
    mutationFn: (fmt: string) =>
      authedJson<{ ok: true }>(`/api/admin/spec-definitions/${spec.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          output_config: fmt.trim()
            ? { ...(spec.output_config ?? {}), name_format: fmt.trim() }
            : { ...(spec.output_config ?? {}), name_format: undefined },
        }),
      }),
    onSuccess: () => {
      toast.success("Formato guardado");
      setIsDirty(false);
      queryClient.invalidateQueries({ queryKey: ["admin", "specs-por-categoria"] });
    },
    onError: () => toast.error("Error guardando el formato"),
  });

  // Preview con value ejemplo. Si la spec tiene uso, fingimos un value real.
  const exampleValue = spec.tipo === "bool" ? "Sí" : spec.tipo === "number" ? "1234" : "valor";
  const exampleUnit = spec.unidad ?? "";
  const preview = value.trim()
    ? value.replace("{value}", exampleValue).replace("{unidad}", exampleUnit)
    : exampleValue;

  return (
    <div className="space-y-2">
      <h3 className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
        Formato en título auto
      </h3>
      <div className="text-xs text-muted-foreground">
        Cómo se renderiza este spec cuando lo insertás como{" "}
        <code className="bg-muted px-1 rounded font-mono">{`{spec:${spec.label}}`}</code>
        {" "}en el template del nombre. Placeholders:{" "}
        <code className="bg-muted px-1 rounded font-mono">{`{value}`}</code>,{" "}
        <code className="bg-muted px-1 rounded font-mono">{`{unidad}`}</code>.
      </div>

      <input
        type="text"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setIsDirty(true);
        }}
        placeholder={`Ej: Potencia {value} ${spec.unidad ?? "unidades"}`}
        className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
      />

      <div className="text-xs">
        <span className="text-muted-foreground">Preview:</span>{" "}
        <span className="text-ink font-medium">{preview}</span>
        {!value.trim() && (
          <span className="text-muted-foreground italic ml-1">(default: solo el valor)</span>
        )}
      </div>

      <div className="flex items-center gap-2 pt-1">
        <Button
          size="sm"
          disabled={!isDirty || saveMutation.isPending}
          onClick={() => saveMutation.mutate(value)}
        >
          {saveMutation.isPending ? "Guardando…" : "Guardar formato"}
        </Button>
        {isDirty && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setValue(current);
              setIsDirty(false);
            }}
          >
            Descartar
          </Button>
        )}
      </div>
    </div>
  );
}
