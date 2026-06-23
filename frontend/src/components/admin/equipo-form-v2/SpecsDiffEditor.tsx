/**
 * Specs editor para el form V2 de equipos.
 *
 * Layout (#291 Fase C):
 *  - Si la categoría tiene spec_templates definidos, los template-bound
 *    specs aparecen primero en el orden de `prioridad` del template.
 *    Su label es read-only (gestionado en /admin/equipos/specs), solo
 *    se edita el value. El tipo del template guía el input (texto,
 *    número con sufijo, enum como select, bool como checkbox).
 *  - Abajo de un divider quedan los specs "custom" — los que el admin
 *    cargó manualmente o vienen del autocompletar y no tienen template.
 *    Estos sí pueden reordenarse con drag-drop, renombrarse y borrarse.
 *  - "Agregar" suma un spec custom al final.
 *  - Propuestos del autocompletar siguen mostrándose arriba con UI de diff.
 *
 * Por qué template-bound no es drag-drop: el orden viene de la prioridad
 * en /admin/equipos/specs (Fase A). Si el admin quiere cambiar el orden,
 * lo hace ahí — así un cambio se aplica a TODOS los equipos de la
 * categoría, no a uno solo.
 */

import { Trash2, GripVertical, BookmarkCheck } from "lucide-react";
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
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { Input } from "@/design-system/ui/input";
import { Button } from "@/design-system/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import type { SpecTemplate } from "@/lib/admin/api";

import { type Spec, sameLabel, extractNumericPart } from "./spec-helpers";
import { TablaValueInput } from "./TablaValueInput";

const lower = (s: string) => s.trim().toLowerCase();

export function SpecsDiffEditor({
  specs,
  propuestos,
  onChange,
  onAceptarPropuesto,
  onDescartarPropuesto,
  templateItems,
}: {
  specs: Spec[];
  propuestos: Spec[];
  onChange: (s: Spec[]) => void;
  onAceptarPropuesto: (s: Spec) => void;
  onDescartarPropuesto: (s: Spec) => void;
  /** #291 Fase C: items del template de la categoría dominante, ya
   *  ordenados por prioridad. Los specs cuyo label matchea aparecen
   *  primero en este orden. */
  templateItems?: SpecTemplate[];
}) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  // Lookup del template por spec_key (exacto) y por label (fallback).
  const tmplByKey = new Map<string, SpecTemplate>();
  const tmplByLabel = new Map<string, SpecTemplate>();
  for (const t of templateItems ?? []) {
    if (t.spec_key) tmplByKey.set(t.spec_key, t);
    if (t.label?.trim()) tmplByLabel.set(lower(t.label), t);
  }
  const findTmplForPropuesto = (s: Spec): SpecTemplate | undefined =>
    (s.spec_key ? tmplByKey.get(s.spec_key) : undefined) ?? tmplByLabel.get(lower(s.label));

  // Particionar specs en "del template" y "custom".
  // El orden del template-bound viene de templateItems (prioridad ASC).
  //
  // Importante: si un template item NO tiene match en specs[] (porque el
  // useEffect de EquipoFormDialogV2 no ha rellenado specs vacías todavía,
  // o por algún edge case), igual lo renderizamos con un "ghost spec"
  // (id derivado del spec_def_id). Cuando el admin edita el valor por
  // primera vez, updateSpec lo materializa en specs[]. Esto asegura que
  // el form siempre muestre todos los specs disponibles del template,
  // independiente de timing/sincronización.
  const specByLabel = new Map<string, Spec>();
  for (const s of specs) specByLabel.set(lower(s.label), s);

  const templateBound: Array<{ spec: Spec; tmpl: SpecTemplate; ghost: boolean }> = [];
  for (const t of templateItems ?? []) {
    if (!t.label?.trim()) continue;
    const existing = specByLabel.get(lower(t.label));
    if (existing) {
      templateBound.push({ spec: existing, tmpl: t, ghost: false });
    } else {
      // Ghost: spec todavía no materializado en specs[]. El id usa
      // spec_def_id como discriminador para que updateSpec lo encuentre.
      templateBound.push({
        spec: { id: `tmpl-${t.spec_def_id}`, label: t.label, value: "" },
        tmpl: t,
        ghost: true,
      });
    }
  }
  const templateBoundIds = new Set(templateBound.filter((x) => !x.ghost).map((x) => x.spec.id));
  const custom = specs.filter((s) => !templateBoundIds.has(s.id));

  const updateSpec = (id: string, patch: Partial<Spec>) => {
    // Si el id corresponde a un spec ya en specs[], update normal.
    if (specs.some((s) => s.id === id)) {
      onChange(specs.map((s) => (s.id === id ? { ...s, ...patch } : s)));
      return;
    }
    // Ghost: materializar agregando al specs[] con el label del template.
    const ghost = templateBound.find((x) => x.ghost && x.spec.id === id);
    if (!ghost) return;
    onChange([...specs, { id, label: ghost.tmpl.label, value: "", ...patch }]);
  };
  const removeSpec = (id: string) => onChange(specs.filter((s) => s.id !== id));
  // addSpec removido: las specs se administran desde Gear Compatibility.
  // Acá solo se cargan valores para las del template.

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const customIds = custom.map((s) => s.id);
    const oldIdx = customIds.indexOf(active.id as string);
    const newIdx = customIds.indexOf(over.id as string);
    if (oldIdx === -1 || newIdx === -1) return;
    const reorderedCustom = arrayMove(custom, oldIdx, newIdx);
    // Reconstruir el array global preservando los template-bound en su lugar
    // (el lookup por label en render no depende del orden del array, pero
    // mantenemos un array consistente: primero los template-bound en orden
    // del template, después los custom reordenados).
    const next = [...templateBound.map((x) => x.spec), ...reorderedCustom];
    onChange(next);
  };

  // Total incluye ghosts (templateItems no materializados aún en specs[]).
  const totalCount = templateBound.length + custom.length;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {totalCount > 0 && (
            <>
              {totalCount} {totalCount === 1 ? "ítem" : "ítems"}
              {templateBound.length > 0 && custom.length > 0 && (
                <span className="ml-1.5 opacity-60">
                  · {templateBound.length} del template + {custom.length} legacy
                </span>
              )}
            </>
          )}
        </span>
      </div>

      {/* Propuestos (del autocompletar) — sección oculta.
          Los parsers bespoke llenan el template directamente; lo que no
          matchea no aporta valor visible al admin. El estado y la lógica
          de auto-apply siguen activos en EquipoFormDialogV2. */}

      {/* Sección template-bound */}
      {templateBound.length > 0 && (
        <div className="rounded-md border hairline bg-muted/20 p-2 space-y-1">
          <div className="flex items-center gap-1.5 text-2xs uppercase tracking-wider text-muted-foreground px-0.5">
            <BookmarkCheck className="h-3 w-3" />
            Del template ({templateBound.length})
          </div>
          {templateBound.map(({ spec, tmpl }) => (
            <TemplateBoundRow
              key={spec.id}
              spec={spec}
              tmpl={tmpl}
              onUpdate={(patch) => updateSpec(spec.id, patch)}
            />
          ))}
        </div>
      )}

      {/* Sección custom (drag-drop). Mostramos warning si un custom colide
          con una spec oficial del catálogo global (mismo label normalizado
          o spec_key parecido) — sugiere usar la spec del template. */}
      {custom.length > 0 && (
        <div className="space-y-1">
          {templateBound.length > 0 && (
            <div className="text-2xs uppercase tracking-wider text-muted-foreground px-0.5">
              Custom ({custom.length}) · arrastrá para reordenar
            </div>
          )}
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext items={custom.map((s) => s.id)} strategy={verticalListSortingStrategy}>
              <div className="space-y-1">
                {custom.map((s) => {
                  // ¿Colide con una spec oficial del template? (label match
                  // case-insensitive ignorando paréntesis y "/" extras).
                  const norm = normalizeForCollision(s.label);
                  const tmplCollision = (templateItems ?? []).find(
                    (t) => normalizeForCollision(t.label) === norm,
                  );
                  return (
                    <CustomSortableRow
                      key={s.id}
                      spec={s}
                      onUpdate={(patch) => updateSpec(s.id, patch)}
                      onRemove={() => removeSpec(s.id)}
                      tmplCollision={tmplCollision ?? null}
                    />
                  );
                })}
              </div>
            </SortableContext>
          </DndContext>
        </div>
      )}

      {totalCount === 0 && propuestos.length === 0 && (
        <p className="text-xs text-muted-foreground italic">Sin ítems.</p>
      )}
    </div>
  );
}

// ── Template-bound row (label read-only, valor type-aware) ──────────────

function TemplateBoundRow({
  spec,
  tmpl,
  onUpdate,
}: {
  spec: Spec;
  tmpl: SpecTemplate;
  onUpdate: (patch: Partial<Spec>) => void;
}) {
  const validation = validateSpecValue(tmpl, spec.value);
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] items-start gap-2">
      <div className="min-w-0 text-xs pt-1.5">
        <span className="text-ink">{tmpl.label}</span>
        {tmpl.obligatorio && <span className="text-destructive ml-0.5">*</span>}
        {tmpl.ayuda && (
          <div className="text-2xs text-muted-foreground truncate" title={tmpl.ayuda}>
            {tmpl.ayuda}
          </div>
        )}
      </div>
      <div className="space-y-0.5">
        <TypedValueInput tmpl={tmpl} value={spec.value} onChange={(v) => onUpdate({ value: v })} />
        {validation.message && (
          <div
            className={
              "text-2xs " + (validation.severity === "error" ? "text-destructive" : "text-amber")
            }
          >
            {validation.severity === "error" ? "✗ " : "⚠ "}
            {validation.message}
          </div>
        )}
      </div>
    </div>
  );
}

/** Validación inline para mostrar feedback al admin mientras edita.
 *  La validación authoritative vive en backend; esta es solo visual
 *  preventiva para que el admin no termine pegando algo que falle al
 *  guardar. */
function validateSpecValue(
  tmpl: SpecTemplate,
  value: string,
): { severity?: "error" | "warn"; message?: string } {
  const v = (value ?? "").trim();
  if (!v) {
    if (tmpl.obligatorio) {
      return { severity: "warn", message: "Obligatorio" };
    }
    return {};
  }
  if (tmpl.tipo === "number") {
    // Acepta number con unidad como sufijo: "640 g" → match en \d+
    if (!/^[+-]?\d+(\.\d+)?(\s+\S+)?$/.test(v)) {
      return { severity: "error", message: "Valor numérico (ej. 640 o 640 g)" };
    }
  }
  if (tmpl.tipo === "rango") {
    // Tolera prefijo (f/2.8) o sufijo (24-70 mm). Solo chequea que tenga
    // al menos un número.
    if (!/\d/.test(v)) {
      return { severity: "error", message: "Faltan números — ej. '50' o '24-70'" };
    }
  }
  if (tmpl.tipo === "wxh") {
    const nums = v.match(/\d+(\.\d+)?/g) ?? [];
    if (nums.length < 2) {
      return { severity: "error", message: "Necesita 2 números (ancho × alto)" };
    }
  }
  if (tmpl.tipo === "wxhxd") {
    const nums = v.match(/\d+(\.\d+)?/g) ?? [];
    if (nums.length < 3) {
      return { severity: "error", message: "Necesita 3 números (W × H × D)" };
    }
  }
  if (tmpl.tipo === "enum" && tmpl.enum_options?.length) {
    if (!tmpl.enum_options.includes(v)) {
      return {
        severity: "warn",
        message: `Valor no está en opciones (${tmpl.enum_options.slice(0, 3).join(", ")}…)`,
      };
    }
  }
  if (tmpl.tipo === "multi_enum" && tmpl.enum_options?.length) {
    try {
      const arr = v.startsWith("[") ? JSON.parse(v) : v.split(",").map((s) => s.trim());
      if (Array.isArray(arr)) {
        const opts = new Set(tmpl.enum_options);
        const invalid = arr.filter((x) => typeof x === "string" && !opts.has(x));
        if (invalid.length > 0) {
          return {
            severity: "warn",
            message: `Fuera de opciones: ${invalid.slice(0, 3).join(", ")}`,
          };
        }
      }
    } catch {
      return { severity: "error", message: "JSON inválido" };
    }
  }
  if (tmpl.tipo === "tabla") {
    if (v.startsWith("[")) {
      try {
        const parsed = JSON.parse(v);
        if (!Array.isArray(parsed)) {
          return { severity: "error", message: "Tabla debe ser array de filas" };
        }
      } catch {
        return { severity: "error", message: "JSON de tabla inválido" };
      }
    }
  }
  return {};
}

function TypedValueInput({
  tmpl,
  value,
  onChange,
}: {
  tmpl: SpecTemplate;
  value: string;
  onChange: (v: string) => void;
}) {
  if (tmpl.tipo === "number") {
    return <NumericValueInput value={value} unidad={tmpl.unidad ?? ""} onChange={onChange} />;
  }

  if (tmpl.tipo === "rango" && tmpl.unidad) {
    return <RangoValueInput value={value} unidad={tmpl.unidad} onChange={onChange} />;
  }

  if ((tmpl.tipo === "wxh" || tmpl.tipo === "wxhxd") && tmpl.unidad) {
    const axes = tmpl.tipo === "wxh" ? 2 : 3;
    return <MedidasValueInput value={value} unidad={tmpl.unidad} axes={axes} onChange={onChange} />;
  }

  if (tmpl.tipo === "multi_enum" && tmpl.enum_options && tmpl.enum_options.length > 0) {
    return <MultiEnumValueInput value={value} options={tmpl.enum_options} onChange={onChange} />;
  }

  if (tmpl.tipo === "enum" && tmpl.enum_options && tmpl.enum_options.length > 0) {
    return (
      <Select value={value || undefined} onValueChange={onChange}>
        <SelectTrigger className="text-xs h-8">
          <SelectValue placeholder="Elegir…" />
        </SelectTrigger>
        <SelectContent>
          {tmpl.enum_options.map((opt) => (
            <SelectItem key={opt} value={opt}>
              {opt}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }

  if (tmpl.tipo === "bool") {
    return <BoolValueInput value={value} onChange={onChange} />;
  }

  if (tmpl.tipo === "tabla" && tmpl.tabla_columnas?.length) {
    return <TablaValueInput value={value} columnas={tmpl.tabla_columnas} onChange={onChange} />;
  }

  // string (default)
  return (
    <Input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Valor"
      className="text-xs"
    />
  );
}

// ── Custom row (drag-drop + label/value libres) ─────────────────────────

/** Normaliza un label para detectar colisión: lowercase, sin paréntesis
 *  finales, sin separadores "/" o "-", colapsa espacios. Ej:
 *    "Línea / serie" → "linea serie"
 *    "Formato de sensor" → "formato de sensor"
 *    "Peso (g)" → "peso" */
function normalizeForCollision(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .replace(/\s*\([^)]*\)\s*$/, "")
    .replace(/[/\-_]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function CustomSortableRow({
  spec,
  onUpdate,
  onRemove,
  tmplCollision,
}: {
  spec: Spec;
  onUpdate: (patch: Partial<Spec>) => void;
  onRemove: () => void;
  /** Si esta spec custom colide con una del template, viene seteado. */
  tmplCollision: SpecTemplate | null;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: spec.id,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="space-y-0.5">
      <div className="flex gap-1 items-center bg-background">
        <button
          type="button"
          className="cursor-grab active:cursor-grabbing text-muted-foreground/40 hover:text-muted-foreground touch-none px-0.5"
          {...attributes}
          {...listeners}
          tabIndex={-1}
        >
          <GripVertical className="h-3.5 w-3.5" />
        </button>
        <Input
          value={spec.label}
          onChange={(e) => onUpdate({ label: e.target.value })}
          placeholder="Spec"
          className={"text-xs " + (tmplCollision ? "border-amber/60" : "")}
        />
        <Input
          value={spec.value}
          onChange={(e) => onUpdate({ value: e.target.value })}
          placeholder="Valor"
          className="text-xs"
        />
        <Button type="button" size="icon" variant="ghost" onClick={onRemove}>
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
      {tmplCollision && (
        <div className="ml-6 text-2xs text-amber italic">
          ⚠ Existe la spec oficial <strong>"{tmplCollision.label}"</strong> en el template —
          eliminala y usá la del template para que entre al sistema estructurado.
        </div>
      )}
    </div>
  );
}

// ── NumericValueInput (Fase B) ──────────────────────────────────────────

// ── RangoValueInput (#calidad-datos) ────────────────────────────────────
// Dos inputs separados: min y max. Si max queda vacío, se guarda como valor
// fijo (ej. "50 mm"). Si los dos están, se guarda como rango ("24-70 mm").
// La BD almacena el string final con unidad como sufijo.

function parseRango(raw: string): { min: string; max: string } {
  // Acepta tanto sufijo ("24-70 mm") como prefijo ("f/24-70"). El regex
  // encuentra el primer par de números en el string, ignorando la unidad
  // antes/después.
  const match = /(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?/.exec(raw);
  return {
    min: match?.[1] ?? "",
    max: match?.[2] ?? "",
  };
}

/** Algunas unidades se escriben antes del número (f/, $, €) en lugar de
 *  después (mm, kg, °). Detección por convención: termina en "/" o
 *  empieza con un símbolo monetario. */
function isPrefixUnit(unidad: string): boolean {
  const u = unidad.trim();
  if (!u) return false;
  return u.endsWith("/") || /^[$€£¥]/.test(u);
}

function RangoValueInput({
  value,
  unidad,
  onChange,
}: {
  value: string;
  unidad: string;
  onChange: (v: string) => void;
}) {
  const { min, max } = parseRango(value);
  const prefix = isPrefixUnit(unidad);

  const commit = (nextMin: string, nextMax: string) => {
    const cleanMin = nextMin.trim();
    const cleanMax = nextMax.trim();
    if (!cleanMin) {
      onChange("");
      return;
    }
    const rango = cleanMax ? `${cleanMin}-${cleanMax}` : cleanMin;
    onChange(prefix ? `${unidad}${rango}` : `${rango} ${unidad}`);
  };

  const unitSpan = (
    <span className="text-2xs uppercase tracking-wider text-muted-foreground">{unidad}</span>
  );

  return (
    <div className="flex items-center gap-1.5">
      {prefix && unitSpan}
      <Input
        type="number"
        inputMode="decimal"
        step="any"
        value={min}
        onChange={(e) => commit(e.target.value, max)}
        className="text-xs w-16"
        aria-label="Valor (o mínimo si es rango)"
      />
      <span className="text-xs text-muted-foreground select-none">–</span>
      <Input
        type="number"
        inputMode="decimal"
        step="any"
        value={max}
        onChange={(e) => commit(min, e.target.value)}
        className="text-xs w-24 placeholder:text-muted-foreground/40 placeholder:italic placeholder:text-2xs"
        placeholder="vacío si es fijo"
        aria-label="Valor máximo (vacío si es fijo)"
      />
      {!prefix && unitSpan}
    </div>
  );
}

// ── MedidasValueInput (wxh / wxhxd) ─────────────────────────────────────
// 2 o 3 inputs numéricos separados por "×" con la unidad al final (o al
// inicio si es unidad prefijo). Storage: "6144×3240 px" o "129.7×84.5×77.8 mm".

function parseMedidas(raw: string, axes: 2 | 3): string[] {
  const matches = raw.match(/\d+(?:\.\d+)?/g) ?? [];
  const out = matches.slice(0, axes);
  while (out.length < axes) out.push("");
  return out;
}

function MedidasValueInput({
  value,
  unidad,
  axes,
  onChange,
}: {
  value: string;
  unidad: string;
  axes: 2 | 3;
  onChange: (v: string) => void;
}) {
  const parts = parseMedidas(value, axes);
  const prefix = isPrefixUnit(unidad);

  const commit = (idx: number, next: string) => {
    const updated = [...parts];
    updated[idx] = next.trim();
    // Si ningún input tiene valor, limpiamos.
    if (updated.every((p) => !p)) {
      onChange("");
      return;
    }
    // Si algún input está vacío, lo dejamos vacío en el join (queda como "×")
    // — usuario tiene que completar los que faltan para que se vea bien.
    const joined = updated.join("×");
    onChange(prefix ? `${unidad}${joined}` : `${joined} ${unidad}`);
  };

  const unitChip = (
    <span className="text-2xs uppercase tracking-wider text-muted-foreground">{unidad}</span>
  );

  return (
    <div className="flex items-center gap-1">
      {prefix && unitChip}
      {parts.map((p, i) => (
        <div key={i} className="flex items-center gap-1">
          <Input
            type="number"
            inputMode="decimal"
            step="any"
            value={p}
            onChange={(e) => commit(i, e.target.value)}
            className="text-xs w-16 text-center"
            aria-label={`Medida ${i + 1} de ${axes}`}
          />
          {i < axes - 1 && <span className="text-xs text-muted-foreground select-none">×</span>}
        </div>
      ))}
      {!prefix && unitChip}
    </div>
  );
}

// ── MultiEnumValueInput ─────────────────────────────────────────────────
// Lista de checkboxes (toggleable chips) — el equipo puede tener varios.
// Storage: JSON array como string ("[\"Wi-Fi\",\"USB-C\"]") o coma-separado.
// Acá usamos coma-separado para mantenerlo legible en BD.

function parseMultiEnum(raw: string): Set<string> {
  if (!raw.trim()) return new Set();
  // Soporta tanto JSON array como coma-separado (legacy / migración).
  if (raw.trim().startsWith("[")) {
    try {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) return new Set(arr.map(String));
    } catch {
      /* fall through */
    }
  }
  return new Set(
    raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  );
}

function MultiEnumValueInput({
  value,
  options,
  onChange,
}: {
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  const selected = parseMultiEnum(value);

  const toggle = (opt: string) => {
    const next = new Set(selected);
    if (next.has(opt)) next.delete(opt);
    else next.add(opt);
    const arr = options.filter((o) => next.has(o)); // preserva el orden del template
    onChange(arr.join(", "));
  };

  return (
    <div className="flex flex-wrap gap-1">
      {options.map((opt) => {
        const isSelected = selected.has(opt);
        return (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs transition ${
              isSelected
                ? "border-amber bg-amber-soft text-ink"
                : "border-ink/15 bg-background text-muted-foreground hover:border-ink/30"
            }`}
            aria-pressed={isSelected}
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}

function NumericValueInput({
  value,
  unidad,
  onChange,
}: {
  value: string;
  /** Unidad opcional — si está vacía, no se concatena ningún sufijo. */
  unidad: string;
  onChange: (v: string) => void;
}) {
  const numericPart = extractNumericPart(value);
  const hasUnidad = !!unidad.trim();
  const prefix = hasUnidad && isPrefixUnit(unidad);
  return (
    <div className="relative">
      <Input
        type="number"
        inputMode="decimal"
        step="any"
        value={numericPart}
        onChange={(e) => {
          const num = e.target.value;
          if (!num.trim()) {
            onChange("");
            return;
          }
          if (!hasUnidad) {
            onChange(num);
            return;
          }
          onChange(prefix ? `${unidad}${num}` : `${num} ${unidad}`);
        }}
        placeholder="0"
        className={`text-xs ${hasUnidad ? (prefix ? "pl-10" : "pr-12") : ""}`}
      />
      {hasUnidad && (
        <span
          className={`pointer-events-none absolute inset-y-0 flex items-center text-2xs uppercase tracking-wider text-muted-foreground ${
            prefix ? "left-2" : "right-2"
          }`}
          aria-hidden
        >
          {unidad}
        </span>
      )}
    </div>
  );
}

// ── BoolValueInput ─────────────────────────────────────────────────────
// Toggle segmentado Sí/No en lugar de checkbox — la casilla vacía leía
// como "no determinado" cuando en realidad significaba "No". Acá ambas
// opciones son visualmente explícitas; cuando ninguna está activa el
// valor está realmente sin determinar.

function isBoolYes(v: string): boolean {
  const t = v.trim().toLowerCase();
  return t === "sí" || t === "si" || t === "true" || t === "1";
}
function isBoolNo(v: string): boolean {
  const t = v.trim().toLowerCase();
  return t === "no" || t === "false" || t === "0";
}

function BoolValueInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const yes = isBoolYes(value);
  const no = isBoolNo(value);
  return (
    <div className="inline-flex rounded-md border hairline overflow-hidden text-xs">
      <button
        type="button"
        onClick={() => onChange(yes ? "" : "Sí")}
        className={
          "px-3 py-1 transition border-r hairline " +
          (yes
            ? "bg-verde/10 text-verde font-medium"
            : "bg-background text-muted-foreground hover:bg-muted/40")
        }
        aria-pressed={yes}
      >
        Sí
      </button>
      <button
        type="button"
        onClick={() => onChange(no ? "" : "No")}
        className={
          "px-3 py-1 transition " +
          (no
            ? "bg-muted text-ink font-medium"
            : "bg-background text-muted-foreground hover:bg-muted/40")
        }
        aria-pressed={no}
      >
        No
      </button>
    </div>
  );
}
