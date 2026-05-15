/**
 * Builder del template de nombre público por categoría.
 *
 * Diseño simple: el dueño escribe el template directo como texto, e inserta
 * placeholders desde una paleta. Cero drag-and-drop, cero chips — todo es
 * un string editable.
 *
 * Sintaxis del template:
 *   Camara {marca} {modelo} ({spec:Lens mount}) {spec:Formato de sensor}
 *
 * Placeholders soportados: {marca}, {modelo}, {tipo}, {nombre} + {spec:Label}
 * para cualquier spec del template de la categoría.
 */

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Tag, Plus } from "lucide-react";

import { adminApi, type SpecTemplate } from "@/lib/admin/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { renderNombrePublicoTemplate } from "@/lib/equipment/nombre-template";

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
  const [template, setTemplate] = useState<string>(initialTemplate ?? "");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Si el initialTemplate cambia (después de un save o navegación), sincronizar.
  useEffect(() => {
    setTemplate(initialTemplate ?? "");
  }, [initialTemplate]);

  /** Inserta un placeholder en la posición del cursor (o al final si no hay
   *  selección activa). Agrega espacio antes/después si no hay para que no se
   *  pegue al texto adyacente. */
  function insertPlaceholder(placeholder: string) {
    const ta = textareaRef.current;
    const cursor = ta?.selectionStart ?? template.length;
    const before = template.slice(0, cursor);
    const after = template.slice(cursor);
    const needsSpaceBefore = before.length > 0 && !before.endsWith(" ") && !before.endsWith("(");
    const needsSpaceAfter = after.length > 0 && !after.startsWith(" ") && !after.startsWith(")");
    const insertion = `${needsSpaceBefore ? " " : ""}${placeholder}${needsSpaceAfter ? " " : ""}`;
    const next = before + insertion + after;
    setTemplate(next);
    // Re-foco y mover cursor justo después de lo insertado
    requestAnimationFrame(() => {
      if (!ta) return;
      ta.focus();
      const pos = cursor + insertion.length;
      ta.setSelectionRange(pos, pos);
    });
  }

  const saveMut = useMutation({
    mutationFn: (tpl: string) =>
      adminApi.adminUpdateCategoria(categoriaId, { nombre_publico_template: tpl.trim() || null }),
    onSuccess: () => {
      toast.success("Plantilla de nombre guardada");
      qc.invalidateQueries({ queryKey: ["admin", "categorias"] });
      qc.invalidateQueries({ queryKey: ["categorias"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Preview con datos vivos (selector de equipo real opcional).
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

  const previewEquipo = previewEquipoId
    ? equiposOpts.find((e) => e.id === previewEquipoId)
    : null;

  const previewSpecs = (() => {
    if (!previewSpecsQ.data) {
      return templateSpecs.map((t) => ({ label: t.label, value: `<${t.label}>` }));
    }
    const { specs: values, template: tmpl } = previewSpecsQ.data;
    return tmpl.map((t) => ({
      label: t.label,
      value: values[t.spec_key] ?? "",
    }));
  })();

  const preview = renderNombrePublicoTemplate(template, {
    marca: previewEquipo?.marca ?? "Sony",
    modelo: previewEquipo?.modelo ?? "FX3",
    tipo: categoriaNombre,
    nombre: previewEquipo?.nombre ?? `Ejemplo ${categoriaNombre}`,
    specs: previewSpecs,
  });

  const fixedPlaceholders = [
    { placeholder: "{marca}", label: "marca" },
    { placeholder: "{modelo}", label: "modelo" },
    { placeholder: "{tipo}", label: "tipo" },
    { placeholder: "{nombre}", label: "nombre interno" },
  ];

  const isDirty = template.trim() !== (initialTemplate ?? "").trim();

  return (
    <div className="rounded-md border hairline overflow-hidden">
      <header className="px-3 py-2 text-xs font-mono uppercase tracking-widest text-muted-foreground border-b hairline bg-muted/30 flex items-center gap-2">
        <Tag className="h-3.5 w-3.5" />
        Plantilla del nombre público
      </header>

      <div className="p-3 space-y-3">
        <div>
          <div className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider mb-1">
            Template — escribí libre, insertá placeholders donde quieras
          </div>
          <Textarea
            ref={textareaRef}
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            placeholder="Ej: Camara {marca} {modelo} ({spec:Lens mount}) {spec:Formato de sensor}"
            rows={2}
            className="font-mono text-sm"
          />
          <p className="text-[10px] text-muted-foreground mt-1">
            Sintaxis: <code className="font-mono">{"{marca}"}</code>, <code className="font-mono">{"{modelo}"}</code>, <code className="font-mono">{"{tipo}"}</code>, <code className="font-mono">{"{nombre}"}</code> y <code className="font-mono">{"{spec:Label}"}</code>.
            Para specs tipo tabla: <code className="font-mono">{"{spec:Label.columna}"}</code> extrae una sola celda.
          </p>
        </div>

        <div>
          <div className="text-[11px] text-muted-foreground font-mono uppercase tracking-wider mb-1">
            Insertar — click para agregar en la posición del cursor
          </div>
          <div className="flex flex-wrap gap-1.5">
            {fixedPlaceholders.map((p) => (
              <button
                key={p.placeholder}
                type="button"
                onClick={() => insertPlaceholder(p.placeholder)}
                className="inline-flex items-center gap-1 rounded border hairline px-2 py-0.5 font-mono text-[11px] text-ink hover:bg-amber-soft transition"
                title={`Insertar ${p.placeholder}`}
              >
                <Plus className="h-3 w-3" /> {p.label}
              </button>
            ))}
            {templateSpecs.map((t) => {
              const ph = `{spec:${t.label}}`;
              const cols = t.tabla_columnas ?? [];
              return (
                <div key={t.id} className="inline-flex flex-col gap-0.5">
                  <button
                    type="button"
                    onClick={() => insertPlaceholder(ph)}
                    className="inline-flex items-center gap-1 rounded border hairline border-amber/40 bg-amber-soft/30 px-2 py-0.5 font-mono text-[11px] text-ink hover:bg-amber-soft transition"
                    title={`Insertar ${ph}${t.tipo === "tabla" ? " — devuelve toda la tabla formateada" : ""}`}
                  >
                    <Plus className="h-3 w-3" /> {t.label}
                  </button>
                  {/* Si la spec es tabla, ofrecer también las columnas como
                      placeholders separados (extraen una celda específica). */}
                  {t.tipo === "tabla" && cols.length > 0 && (
                    <div className="inline-flex flex-wrap gap-0.5 ml-3">
                      {cols.map((c) => {
                        const subPh = `{spec:${t.label}.${c.key}}`;
                        return (
                          <button
                            key={c.key}
                            type="button"
                            onClick={() => insertPlaceholder(subPh)}
                            className="inline-flex items-center gap-0.5 rounded border hairline border-amber/30 bg-background px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground hover:text-ink hover:bg-amber-soft/30 transition"
                            title={`Insertar ${subPh} — extrae solo la columna ${c.label} de la primera fila`}
                          >
                            <Plus className="h-2.5 w-2.5" /> {c.key}
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
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
            onClick={() => saveMut.mutate(template)}
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
