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
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { GripVertical, X, Plus, Tag } from "lucide-react";

import { adminApi, type SpecTemplate } from "@/lib/admin/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { renderNombrePublicoTemplate } from "@/lib/equipment/nombre-template";

type Token = {
  id: string;        // único para dnd-kit
  placeholder: string;  // ej. "{marca}", "{spec:Montura}"
  label: string;     // texto visible en el chip
};

/** Parsea un template string a tokens. Literales entre placeholders se
 *  concatenan al prefijo si están al principio, o se ignoran (limitación
 *  intencional del MVP — los nombres complejos suelen ser placeholder+espacio). */
function parseTemplate(tpl: string): { prefix: string; tokens: Token[] } {
  if (!tpl.trim()) return { prefix: "", tokens: [] };
  // Match placeholders {x} y devuelve también lo que hay antes del primero.
  const re = /\{([^}]+)\}/g;
  const tokens: Token[] = [];
  let prefix = "";
  let firstMatch = true;
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  let counter = 0;
  while ((m = re.exec(tpl)) !== null) {
    const literalBefore = tpl.slice(lastIndex, m.index);
    if (firstMatch) {
      prefix = literalBefore.trim();
      firstMatch = false;
    }
    const ph = m[0];
    tokens.push({
      id: `t-${counter++}`,
      placeholder: ph,
      label: prettyLabel(ph),
    });
    lastIndex = m.index + m[0].length;
  }
  return { prefix, tokens };
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

function buildTemplate(prefix: string, tokens: Token[]): string {
  const placeholders = tokens.map((t) => t.placeholder).join(" ");
  return prefix.trim() ? `${prefix.trim()} ${placeholders}`.trim() : placeholders;
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
  const [prefix, setPrefix] = useState(parsed.prefix);
  const [tokens, setTokens] = useState<Token[]>(parsed.tokens);

  useEffect(() => {
    setPrefix(parsed.prefix);
    setTokens(parsed.tokens);
  }, [parsed.prefix, parsed.tokens]);

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

  const addToken = (placeholder: string) => {
    setTokens((cur) => [
      ...cur,
      { id: `t-${Date.now()}-${Math.random()}`, placeholder, label: prettyLabel(placeholder) },
    ]);
  };

  const removeToken = (id: string) => setTokens((cur) => cur.filter((t) => t.id !== id));

  const currentTemplate = buildTemplate(prefix, tokens);

  // Detectar qué placeholders ya están usados, para no duplicar en la paleta.
  const usedPlaceholders = new Set(tokens.map((t) => t.placeholder));

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

  // Preview con datos de ejemplo. Si el dueño le pone {spec:Foo} y Foo no
  // existe como label, el render devuelve "" para ese spec.
  const preview = renderNombrePublicoTemplate(currentTemplate, {
    marca: "Sony",
    modelo: "FX3",
    tipo: categoriaNombre,
    nombre: `Ejemplo ${categoriaNombre}`,
    specs: templateSpecs.map((t) => ({ label: t.label, value: `<${t.label}>` })),
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
          <label className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider">
            Prefijo literal (opcional)
          </label>
          <Input
            value={prefix}
            onChange={(e) => setPrefix(e.target.value)}
            placeholder="ej. Cámara, Lente, Luz…"
            className="text-sm h-8 mt-0.5"
          />
        </div>

        <div>
          <div className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider mb-1">
            Tokens (arrastrá para reordenar)
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
                <div className="flex flex-wrap items-center gap-1.5">
                  {prefix.trim() && (
                    <span className="rounded bg-ink/5 px-2 py-1 text-xs text-muted-foreground font-mono">
                      {prefix.trim()}
                    </span>
                  )}
                  {tokens.map((t) => (
                    <TokenChip key={t.id} token={t} onRemove={() => removeToken(t.id)} />
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
                onClick={() => addToken(p.placeholder)}
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
                  onClick={() => addToken(ph)}
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
          <div className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider mb-1">
            Vista previa
          </div>
          <div className="rounded-md border hairline bg-muted/20 px-3 py-2 text-sm text-ink min-h-[2rem] flex items-center">
            {preview ?? (
              <span className="italic text-muted-foreground">
                Sin template → se usa el nombre interno del equipo
              </span>
            )}
          </div>
          <p className="text-[10px] text-muted-foreground mt-1">
            Ejemplo simulado con marca "Sony", modelo "FX3", tipo "{categoriaNombre}". Los specs
            muestran su label entre &lt;…&gt;.
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

function TokenChip({ token, onRemove }: { token: Token; onRemove: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: token.id });
  const style = { transform: CSS.Transform.toString(transform), transition };
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
