/**
 * SpecsTabContent — tab "Ficha técnica" template-based.
 *
 * Reemplaza el viejo editor de specs_json (label/value libre) por inputs
 * específicos según el template de la categoría asignada al equipo.
 *
 * Comportamiento:
 *   - Llama a getEquipoSpecs(id) para traer template + valores actuales.
 *   - Renderea un input por cada spec del template, con el tipo correcto:
 *       string → Input texto
 *       number → Input number
 *       enum   → Select con options
 *       bool   → Checkbox / Switch
 *   - Permite agregar specs "extras" (key/value libre) para campos que
 *     no están en el template.
 *   - "Guardar" llama a putEquipoSpecs(id, dict) que reemplaza todas.
 *
 * Si el equipo no tiene categoría asignada → muestra mensaje pidiendo
 * que asigne categoría primero (no hay template aplicable).
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Trash2, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { adminApi } from "@/lib/admin/api";


type SpecTemplate = {
  template_id: number;
  spec_def_id: number;
  spec_key: string;
  label: string;
  tipo: string;
  unidad: string | null;
  enum_options: string[] | null;
  prioridad: number;
  visible_en_card: boolean;
  visible_en_filtros: boolean;
  visible_en_nombre: boolean;
  obligatorio: boolean;
  ayuda: string | null;
  destacado: boolean;
  categoria_nombre: string;
};


export function SpecsTabContent({ equipoId }: { equipoId: number }) {
  const qc = useQueryClient();
  const specsQ = useQuery({
    queryKey: ["admin", "equipo-specs", equipoId],
    queryFn: () => adminApi.getEquipoSpecs(equipoId),
    enabled: !!equipoId,
  });

  // Valores locales que el usuario edita. Se inicializa desde specsQ.data.
  // Post refactor unificar_specs_definitions: las keys son spec_def_id
  // stringificados ("123": "valor"), no spec_key.
  const [values, setValues] = useState<Record<string, string>>({});
  // Extras: spec_def_ids que tienen value en el equipo pero NO están en el
  // template actual (la asignación se borró, o la categoría cambió). Se
  // muestran read-only; el dueño los puede borrar pero no editarlos
  // libremente — para eso, asignar la spec a la categoría desde
  // /admin/equipos/specs.
  const [extras, setExtras] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!specsQ.data) return;
    const templateDefIds = new Set(specsQ.data.template.map((t) => String(t.spec_def_id)));
    const valsTemplate: Record<string, string> = {};
    const valsExtras: Record<string, string> = {};
    for (const [key, val] of Object.entries(specsQ.data.specs)) {
      if (templateDefIds.has(key)) {
        valsTemplate[key] = val;
      } else {
        valsExtras[key] = val;
      }
    }
    setValues(valsTemplate);
    setExtras(valsExtras);
  }, [specsQ.data]);

  const saveMut = useMutation({
    mutationFn: () => {
      const combined: Record<string, string> = {};
      for (const [k, v] of Object.entries(values)) {
        if (v !== "" && v !== null && v !== undefined) combined[k] = String(v);
      }
      // Conservamos los extras tal cual están — el usuario puede haberlos
      // dejado vacíos para que se borren en el save.
      for (const [k, v] of Object.entries(extras)) {
        if (v !== "" && v !== null && v !== undefined) combined[k] = String(v);
      }
      return adminApi.putEquipoSpecs(equipoId, combined);
    },
    onSuccess: (r) => {
      toast.success(`Specs guardados (${r.specs_count})`);
      qc.invalidateQueries({ queryKey: ["admin", "equipo-specs", equipoId] });
      qc.invalidateQueries({ queryKey: ["admin", "equipos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Agrupar el template por categoría_nombre cuando hay specs de varias
  // categorías (un equipo puede estar en más de una).
  const templateByCategory = useMemo(() => {
    const groups: Record<string, SpecTemplate[]> = {};
    for (const t of specsQ.data?.template ?? []) {
      const cat = t.categoria_nombre;
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(t);
    }
    return groups;
  }, [specsQ.data]);

  if (specsQ.isLoading) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mx-auto mb-2" />
        Cargando template…
      </div>
    );
  }

  const template = specsQ.data?.template ?? [];
  const noCategoria = template.length === 0;

  return (
    <div className="space-y-4">
      <div className="rounded-md border hairline bg-muted/30 px-3 py-2 text-xs">
        <Sparkles className="inline h-3 w-3 mr-1 text-amber" />
        Los specs se rellenan según la <strong>categoría asignada</strong>. Cambialos y los
        nombres públicos se recalculan al guardar.
      </div>

      {noCategoria && (
        <div className="rounded-md border hairline border-amber/40 bg-amber-soft/30 px-3 py-3 text-sm">
          <p className="text-ink">
            Este equipo no tiene categoría asignada todavía.
          </p>
          <p className="text-muted-foreground mt-1 text-xs">
            Asignalo en la pestaña "Categorías" o desde{" "}
            <code className="font-mono">/admin/clasificar</code> para ver los specs
            específicos aplicables (cámara/lente/luz/etc).
          </p>
        </div>
      )}

      {/* Specs del template, agrupados por categoría si hay varias */}
      {Object.entries(templateByCategory).map(([cat, specs]) => (
        <div key={cat} className="rounded-md border hairline bg-background">
          <div className="px-3 py-2 border-b hairline bg-muted/20">
            <Label className="text-xs uppercase tracking-wide text-muted-foreground">
              {cat}
            </Label>
          </div>
          <div className="p-3 grid grid-cols-1 md:grid-cols-2 gap-3">
            {specs.map((t) => {
              const key = String(t.spec_def_id);
              return (
                <SpecInput
                  key={key}
                  template={t}
                  value={values[key] ?? ""}
                  onChange={(v) => setValues((prev) => ({ ...prev, [key]: v }))}
                />
              );
            })}
          </div>
        </div>
      ))}

      {/* Extras — specs huérfanas (sin asignación a la categoría actual).
          Post refactor unificar_specs_definitions: ya no se pueden crear
          extras inline. Para agregar una spec nueva: ir a /admin/equipos/specs
          y crearla en la categoría correspondiente. */}
      {Object.keys(extras).length > 0 && (
        <div className="rounded-md border hairline bg-background">
          <div className="px-3 py-2 border-b hairline bg-muted/20">
            <Label className="text-xs uppercase tracking-wide text-muted-foreground">
              Specs huérfanas (no están en el template de esta categoría)
            </Label>
          </div>
          <div className="p-3 space-y-2">
            {Object.entries(extras).map(([k, v]) => (
              <div key={k} className="flex gap-2 items-center">
                <span className="text-xs font-mono text-muted-foreground w-40 truncate" title={`spec_def_id: ${k}`}>
                  def #{k}
                </span>
                <Input
                  value={v}
                  onChange={(e) =>
                    setExtras((prev) => ({ ...prev, [k]: e.target.value }))
                  }
                  className="flex-1 h-8 text-xs"
                />
                <Button
                  type="button" size="icon" variant="ghost"
                  onClick={() =>
                    setExtras((prev) => {
                      const next = { ...prev }; delete next[k]; return next;
                    })
                  }
                  className="h-7 w-7"
                  title="Borrar este value (la spec_definition queda)"
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))}
            <p className="text-[10px] text-muted-foreground italic mt-2">
              Estos valores existen pero la spec no está asignada a esta categoría.
              Para verla con su label/tipo correcto, asignala desde
              <code className="font-mono mx-1">/admin/equipos/specs</code>.
            </p>
          </div>
        </div>
      )}

      {/* Guardar */}
      <div className="flex justify-end gap-2">
        <Button
          type="button"
          onClick={() => saveMut.mutate()}
          disabled={saveMut.isPending}
        >
          {saveMut.isPending ? (
            <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Guardando…</>
          ) : (
            "Guardar specs"
          )}
        </Button>
      </div>
    </div>
  );
}


/** Renderea un input según el tipo del template. */
function SpecInput({
  template,
  value,
  onChange,
}: {
  template: SpecTemplate;
  value: string;
  onChange: (v: string) => void;
}) {
  const label = (
    <Label className="text-xs uppercase tracking-wide text-muted-foreground flex items-center gap-1">
      {template.label}
      {template.obligatorio && <span className="text-destructive">*</span>}
    </Label>
  );

  // Booleano: switch
  if (template.tipo === "bool") {
    const checked = value === "true" || value === "1" || value === "sí" || value === "yes";
    return (
      <div className="space-y-1">
        {label}
        <div className="flex items-center gap-2 h-9 rounded-md border hairline px-3">
          <Switch checked={checked} onCheckedChange={(v) => onChange(v ? "true" : "false")} />
          <span className="text-xs text-muted-foreground">{checked ? "Sí" : "No"}</span>
        </div>
        {template.ayuda && <p className="text-[10px] text-muted-foreground">{template.ayuda}</p>}
      </div>
    );
  }

  // Enum: select
  if (template.tipo === "enum" && template.enum_options) {
    return (
      <div className="space-y-1">
        {label}
        <Select value={value || "__none"} onValueChange={(v) => onChange(v === "__none" ? "" : v)}>
          <SelectTrigger className="h-9"><SelectValue placeholder="—" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__none">— vacío —</SelectItem>
            {template.enum_options.map((opt) => (
              <SelectItem key={opt} value={opt}>{opt}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {template.ayuda && <p className="text-[10px] text-muted-foreground">{template.ayuda}</p>}
      </div>
    );
  }

  // Number / string: Input
  return (
    <div className="space-y-1">
      {label}
      <div className="relative">
        <Input
          type={template.tipo === "number" ? "number" : "text"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={template.ayuda ?? ""}
          className="h-9"
        />
        {template.unidad && (
          <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-muted-foreground font-mono pointer-events-none">
            {template.unidad}
          </span>
        )}
      </div>
      {template.ayuda && <p className="text-[10px] text-muted-foreground">{template.ayuda}</p>}
    </div>
  );
}
