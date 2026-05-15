/**
 * Builder visual del template de nombre público por categoría.
 *
 * Reemplaza al NombreTemplateDialog viejo. Vive embebido en SpecTemplatesSection
 * (debajo de la tabla de specs) para que el dueño componga el nombre tirando
 * de las mismas specs que está editando.
 *
 * Modelo de tokens:
 *  - El template se parsea en una lista de chips (placeholders) + un literal
 *    inicial opcional (prefijo).
 *  - Cada chip se puede arrastrar para reordenar o sacar con la X.
 *  - Para agregar más, el dueño clickea en los chips de la "paleta" abajo
 *    (marca, modelo, tipo, o cualquier spec de la categoría).
 */

import { useEffect, useMemo, useState } from "react";
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates, horizontalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { GripVertical, X, Plus, Tag } from "lucide-react";

import { adminApi, type SpecTemplate } from "@/lib/admin/api";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { renderNombrePublicoTemplate } from "@/lib/equipment/nombre-template";

type Token =
  | { id: string; kind: "placeholder"; placeholder: string; label: string }
  | { id: string; kind: "literal"; text: string };

let _tokenCounter = 0;
const nextId = () => `t-${++_tokenCounter}-${Date.now().toString(36)}`;

/** Parsea un template string a tokens (placeholders + literales entre ellos).
 *  Los literales preservan los espacios y la puntuación exacta — el dueño
 *  puede meter "-", "(", "f/", etc. en cualquier posición. */
function parseTemplate(tpl: string): { tokens: Token[] } {
  if (!tpl.trim()) return { tokens: [] };
  const re = /\{([^}]+)\}/g;
  const tokens: Token[] = [];
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(tpl)) !== null) {
    const literalBefore = tpl.slice(lastIndex, m.index);
    if (literalBefore && literalBefore !== " ") {
      // Literal antes del placeholder — preservar como token. El espacio
      // simple lo ignoramos (es el separador default cuando no hay literal
      // explícito).
      tokens.push({ id: nextId(), kind: "literal", text: literalBefore });
    }
    tokens.push({
      id: nextId(),
      kind: "placeholder",
      placeholder: m[0],
      label: prettyLabel(m[0]),
    });
    lastIndex = m.index + m[0].length;
  }
  const trailing = tpl.slice(lastIndex);
  if (trailing && trailing !== " ") {
    tokens.push({ id: nextId(), kind: "literal", text: trailing });
  }
  return { tokens };
}

function prettyLabel(placeholder: string): string {
  const inner = placeholder.replace(/^\{|\}$/g, "").trim();
  if (inner.startsWith("spec:")) return inner.slice("spec:".length);
  if (inner === "marca") return "Marca";
  if (inner === "modelo") return "Modelo";
  if (inner === "tipo") return "Tipo (categoría)";
  if (inner === "nombre") return "Nombre interno";
  return inner;
}

function buildTemplate(tokens: Token[]): string {
  // Compose token-by-token. Si tokens consecutivos no tienen un literal entre
  // medio, ponemos un espacio. Si hay literal explícito, se respeta tal cual.
  let out = "";
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];
    const prev = tokens[i - 1];
    if (t.kind === "placeholder") {
      if (prev && prev.kind === "placeholder") out += " ";
      out += t.placeholder;
    } else {
      out += t.text;
    }
  }
  return out.trim();
}

export function NombreTemplateBuilder({
  categoriaId,
  categoriaNombre,
  initialTemplate,
  templateSpecs,
}: {
  categoriaId: number;
  categoriaNombre: string;
  initialTemplate: string | null | undefined;
  templateSpecs: SpecTemplate[];
}) {
  const qc = useQueryClient();
  const parsed = useMemo(() => parseTemplate(initialTemplate ?? ""), [initialTemplate]);
  const [tokens, setTokens] = useState<Token[]>(parsed.tokens);

  useEffect(() => {
    setTokens(parsed.tokens);
  }, [parsed.tokens]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIdx = tokens.findIndex((t) => t.id === active.id);
    const newIdx = tokens.findIndex((t) => t.id === over.id);
    if (oldIdx < 0 || newIdx < 0) return;
    setTokens((items) => arrayMove(items, oldIdx, newIdx));
  };

  const addPlaceholder = (placeholder: string) => {
    setTokens((cur) => [
      ...cur,
      { id: nextId(), kind: "placeholder", placeholder, label: prettyLabel(placeholder) },
    ]);
  };

  /** Inserta un literal vacío en el índice dado (entre chips). Se autoenfoca
   *  para que el dueño tipee sin clicks extra. */
  const insertLiteralAt = (index: number) => {
    const newId = nextId();
    setTokens((cur) => {
      const next = [...cur];
      next.splice(index, 0, { id: newId, kind: "literal", text: "" });
      return next;
    });
    // Esperar al render para enfocar el input recién montado.
    requestAnimationFrame(() => {
      const el = document.querySelector<HTMLInputElement>(`[data-literal-id="${newId}"]`);
      el?.focus();
    });
  };

  const removeToken = (id: string) => setTokens((cur) => cur.filter((t) => t.id !== id));

  const updateLiteral = (id: string, text: string) => {
    setTokens((cur) =>
      cur.map((t) => (t.id === id && t.kind === "literal" ? { ...t, text } : t)),
    );
  };

  const currentTemplate = buildTemplate(tokens);

  // Detectar qué placeholders ya están usados, para no duplicar en la paleta.
  const usedPlaceholders = new Set(
    tokens.filter((t) => t.kind === "placeholder").map((t) => (t as Extract<Token, { kind: "placeholder" }>).placeholder),
  );

  const saveMut = useMutation({
    mutationFn: (template: string) =>
      adminApi.adminUpdateCategoria(categoriaId, { nombre_publico_template: template }),
    onSuccess: () => {
      toast.success("Plantilla de nombre guardada");
      qc.invalidateQueries({ queryKey: ["admin", "categorias"] });
      qc.invalidateQueries({ queryKey: ["categorias"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Selector opcional de equipo real para preview con datos vivos.
  const [previewEquipoId, setPreviewEquipoId] = useState<number | null>(null);
  const equiposQ = useQuery({
    queryKey: ["admin", "equipos", "preview", categoriaNombre],
    queryFn: () => adminApi.listEquipos({ categoria: categoriaNombre, per_page: 100 }),
    staleTime: 60_000,
  });
  const equiposOpts = equiposQ.data?.items ?? [];

  const previewSpecsQ = useQuery({
    queryKey: ["admin", "equipo-specs", previewEquipoId],
    queryFn: () => adminApi.getEquipoSpecs(previewEquipoId!),
    enabled: previewEquipoId != null,
    staleTime: 30_000,
  });

  // Variables para el preview: si hay equipo elegido, usar sus datos reales;
  // sino caer a dummy "Sony FX3" + labels <Foo>.
  const previewEquipo = previewEquipoId
    ? equiposOpts.find((e) => e.id === previewEquipoId)
    : null;
  const previewSpecs = useMemo(() => {
    if (!previewSpecsQ.data) {
      return templateSpecs.map((t) => ({ label: t.label, value: `<${t.label}>` }));
    }
    const { specs: values, template } = previewSpecsQ.data;
    return template.map((t) => ({
      label: t.label,
      value: values[t.spec_key] ?? "",
    }));
  }, [previewSpecsQ.data, templateSpecs]);

  const preview = renderNombrePublicoTemplate(currentTemplate, {
    marca: previewEquipo?.marca ?? "Sony",
    modelo: previewEquipo?.modelo ?? "FX3",
    tipo: categoriaNombre,
    nombre: previewEquipo?.nombre ?? `Ejemplo ${categoriaNombre}`,
    specs: previewSpecs,
  });

  const fixedPlaceholders: { placeholder: string; label: string }[] = [
    { placeholder: "{marca}", label: "Marca" },
    { placeholder: "{modelo}", label: "Modelo" },
    { placeholder: "{tipo}", label: "Tipo (categoría)" },
    { placeholder: "{nombre}", label: "Nombre interno" },
  ];

  const isDirty = currentTemplate !== (initialTemplate ?? "").trim();

  return (
    <div className="rounded-md border hairline overflow-hidden">
      <header className="px-3 py-2 text-xs font-mono uppercase tracking-widest text-muted-foreground border-b hairline bg-muted/30 flex items-center gap-2">
        <Tag className="h-3.5 w-3.5" />
        Plantilla del nombre público
      </header>

      <div className="p-3 space-y-3">
        <div>
          <div className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider mb-1">
            Tokens — arrastrá para reordenar, click en "+" entre chips para insertar texto
          </div>
          {tokens.length === 0 ? (
            <div className="rounded-md border hairline border-dashed bg-muted/20 px-3 py-3 text-[11px] text-muted-foreground italic">
              Sin tokens — clickeá en la paleta de abajo para agregar.
            </div>
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext items={tokens.map((t) => t.id)} strategy={horizontalListSortingStrategy}>
                <div className="flex flex-wrap items-center gap-0.5">
                  <InsertHere onClick={() => insertLiteralAt(0)} />
                  {tokens.map((t, i) => (
                    <div key={t.id} className="flex items-center gap-0.5">
                      <TokenChip
                        token={t}
                        onRemove={() => removeToken(t.id)}
                        onChangeLiteral={(v) => updateLiteral(t.id, v)}
                      />
                      <InsertHere onClick={() => insertLiteralAt(i + 1)} />
                    </div>
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          )}
        </div>

        <div>
          <div className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider mb-1">
            Paleta — click para agregar
          </div>
          <div className="flex flex-wrap gap-1.5">
            {fixedPlaceholders.map((p) => (
              <button
                key={p.placeholder}
                type="button"
                disabled={usedPlaceholders.has(p.placeholder)}
                onClick={() => addPlaceholder(p.placeholder)}
                className="inline-flex items-center gap-1 rounded border hairline px-2 py-0.5 font-mono text-[11px] text-ink hover:bg-amber-soft transition disabled:opacity-40 disabled:cursor-not-allowed"
                title={usedPlaceholders.has(p.placeholder) ? "Ya está en el template" : "Agregar al template"}
              >
                <Plus className="h-3 w-3" /> {p.label}
              </button>
            ))}
            {templateSpecs.map((t) => {
              const ph = `{spec:${t.label}}`;
              const used = usedPlaceholders.has(ph);
              return (
                <button
                  key={t.id}
                  type="button"
                  disabled={used}
                  onClick={() => addPlaceholder(ph)}
                  className="inline-flex items-center gap-1 rounded border hairline border-amber/40 bg-amber-soft/30 px-2 py-0.5 font-mono text-[11px] text-ink hover:bg-amber-soft transition disabled:opacity-40 disabled:cursor-not-allowed"
                  title={used ? "Ya está en el template" : `Agregar spec "${t.label}"`}
                >
                  <Plus className="h-3 w-3" /> {t.label}
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <div className="flex items-baseline justify-between gap-2 mb-1">
            <div className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider">
              Vista previa
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-muted-foreground">Equipo:</span>
              <Select
                value={previewEquipoId != null ? String(previewEquipoId) : "__dummy"}
                onValueChange={(v) => setPreviewEquipoId(v === "__dummy" ? null : Number(v))}
              >
                <SelectTrigger className="h-7 text-xs w-56">
                  <SelectValue placeholder="Ejemplo Sony FX3" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__dummy">Ejemplo (Sony FX3 dummy)</SelectItem>
                  {equiposOpts.map((e) => (
                    <SelectItem key={e.id} value={String(e.id)}>
                      {e.marca} {e.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="rounded-md border hairline bg-muted/20 px-3 py-2 text-sm text-ink min-h-[2rem] flex items-center">
            {preview ?? (
              <span className="italic text-muted-foreground">
                Sin template → se usa el nombre interno del equipo
              </span>
            )}
          </div>
          <p className="text-[10px] text-muted-foreground mt-1">
            {previewEquipo
              ? `Datos reales del equipo "${previewEquipo.nombre}". Los specs vacíos quedan como "".`
              : `Ejemplo simulado con marca "Sony", modelo "FX3", tipo "${categoriaNombre}". Los specs muestran su label entre <…>.`}
          </p>
        </div>

        <div className="flex items-center gap-2 pt-1">
          <Button
            size="sm"
            disabled={!isDirty || saveMut.isPending}
            onClick={() => saveMut.mutate(currentTemplate)}
          >
            {saveMut.isPending ? "Guardando…" : "Guardar plantilla"}
          </Button>
          {isDirty && (
            <span className="text-[10px] text-muted-foreground">
              Cambios sin guardar
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function InsertHere({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group inline-flex items-center justify-center h-6 w-3 hover:w-6 transition-all text-muted-foreground/40 hover:text-ink"
      title="Insertar texto acá"
      aria-label="Insertar texto acá"
    >
      <span className="opacity-0 group-hover:opacity-100 transition-opacity font-mono text-[10px]">+</span>
    </button>
  );
}

function TokenChip({
  token, onRemove, onChangeLiteral,
}: {
  token: Token;
  onRemove: () => void;
  onChangeLiteral: (v: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: token.id });
  const style = { transform: CSS.Transform.toString(transform), transition };

  if (token.kind === "literal") {
    return (
      <div
        ref={setNodeRef}
        style={style}
        className={`inline-flex items-center gap-1 rounded border border-dashed border-muted-foreground/40 bg-muted/30 px-1.5 py-0.5 font-mono text-[11px] text-ink ${
          isDragging ? "opacity-60" : ""
        }`}
        title="Texto literal — editá inline, los espacios cuentan"
      >
        <button
          type="button"
          {...attributes}
          {...listeners}
          className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-ink"
          aria-label="Arrastrar"
        >
          <GripVertical className="h-3 w-3" />
        </button>
        <input
          type="text"
          value={token.text}
          onChange={(e) => onChangeLiteral(e.target.value)}
          placeholder="texto"
          data-literal-id={token.id}
          className="bg-transparent border-0 outline-none focus:outline-none focus:ring-0 px-0.5 font-mono text-[11px] text-ink text-center"
          style={{ width: `${Math.max(2, token.text.length + 1)}ch` }}
        />
        <button
          type="button"
          onClick={onRemove}
          className="text-muted-foreground hover:text-destructive"
          aria-label="Quitar"
        >
          <X className="h-3 w-3" />
        </button>
      </div>
    );
  }

  const isSpec = token.placeholder.startsWith("{spec:");
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[11px] text-ink ${
        isSpec ? "border-amber/40 bg-amber-soft/40" : "border-ink/15 bg-ink/5"
      } ${isDragging ? "opacity-60" : ""}`}
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-ink"
        aria-label="Arrastrar"
      >
        <GripVertical className="h-3 w-3" />
      </button>
      <span>{token.label}</span>
      <button
        type="button"
        onClick={onRemove}
        className="text-muted-foreground hover:text-destructive"
        aria-label="Quitar"
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  );
}
