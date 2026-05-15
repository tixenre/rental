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

import { Plus, Trash2, GripVertical, BookmarkCheck } from "lucide-react";
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import type { SpecTemplate } from "@/lib/admin/api";

import { type Spec, newSpec, sameLabel, extractNumericPart } from "./spec-helpers";

const lower = (s: string) => s.trim().toLowerCase();

export function SpecsDiffEditor({
  specs, propuestos, onChange, onAceptarPropuesto, onDescartarPropuesto,
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

  // Lookup case-insensitive del template por label.
  const tmplByLabel = new Map<string, SpecTemplate>();
  for (const t of templateItems ?? []) {
    if (t.label?.trim()) tmplByLabel.set(lower(t.label), t);
  }

  // Particionar specs en "del template" y "custom".
  // El orden del template-bound viene de templateItems (prioridad ASC).
  const specByLabel = new Map<string, Spec>();
  for (const s of specs) specByLabel.set(lower(s.label), s);

  const templateBound: Array<{ spec: Spec; tmpl: SpecTemplate }> = [];
  for (const t of templateItems ?? []) {
    const s = specByLabel.get(lower(t.label));
    if (s) templateBound.push({ spec: s, tmpl: t });
  }
  const templateBoundIds = new Set(templateBound.map((x) => x.spec.id));
  const custom = specs.filter((s) => !templateBoundIds.has(s.id));

  const updateSpec = (id: string, patch: Partial<Spec>) => {
    onChange(specs.map((s) => s.id === id ? { ...s, ...patch } : s));
  };
  const removeSpec = (id: string) => onChange(specs.filter((s) => s.id !== id));
  const addSpec = () => onChange([...specs, newSpec()]);

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
    const next = [
      ...templateBound.map((x) => x.spec),
      ...reorderedCustom,
    ];
    onChange(next);
  };

  const totalCount = specs.length;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {totalCount > 0 && (
            <>
              {totalCount} {totalCount === 1 ? "ítem" : "ítems"}
              {templateBound.length > 0 && custom.length > 0 && (
                <span className="ml-1.5 opacity-60">
                  · {templateBound.length} del template + {custom.length} custom
                </span>
              )}
            </>
          )}
        </span>
        <Button type="button" size="sm" variant="ghost" onClick={addSpec}>
          <Plus className="h-3 w-3 mr-1" /> Agregar
        </Button>
      </div>

      {/* Propuestos (del autocompletar) */}
      {propuestos.length > 0 && (
        <div className="rounded-md border hairline bg-amber-soft/30 p-2 space-y-1.5">
          <p className="text-[11px] text-ink/70 font-medium">
            ✨ {propuestos.length} {propuestos.length === 1 ? "ítem propuesto" : "ítems propuestos"} del autocompletar
          </p>
          {propuestos.map((s) => {
            const existing = specs.find((x) => sameLabel(x.label, s.label));
            return (
              <div key={s.id} className="flex items-center gap-1.5 text-xs">
                <div className="flex-1 min-w-0">
                  <span className="font-medium">{s.label}:</span>{" "}
                  <span>{s.value}</span>
                  {existing && existing.value !== s.value && (
                    <span className="ml-1 text-muted-foreground line-through">{existing.value}</span>
                  )}
                </div>
                <Button type="button" size="sm" variant="default" className="h-6 px-1.5 text-[10px]"
                  onClick={() => onAceptarPropuesto(s)}>
                  ✓
                </Button>
                <Button type="button" size="sm" variant="outline" className="h-6 px-1.5 text-[10px]"
                  onClick={() => onDescartarPropuesto(s)}>
                  ✗
                </Button>
              </div>
            );
          })}
        </div>
      )}

      {/* Sección template-bound */}
      {templateBound.length > 0 && (
        <div className="rounded-md border hairline bg-muted/20 p-2 space-y-1">
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground px-0.5">
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

      {/* Sección custom (drag-drop) */}
      {custom.length > 0 && (
        <div className="space-y-1">
          {templateBound.length > 0 && (
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground px-0.5">
              Custom ({custom.length}) · arrastrá para reordenar
            </div>
          )}
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={custom.map((s) => s.id)} strategy={verticalListSortingStrategy}>
              <div className="space-y-1">
                {custom.map((s) => (
                  <CustomSortableRow
                    key={s.id}
                    spec={s}
                    onUpdate={(patch) => updateSpec(s.id, patch)}
                    onRemove={() => removeSpec(s.id)}
                  />
                ))}
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
  spec, tmpl, onUpdate,
}: {
  spec: Spec;
  tmpl: SpecTemplate;
  onUpdate: (patch: Partial<Spec>) => void;
}) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] items-center gap-2">
      <div className="min-w-0 text-xs">
        <span className="text-ink">{tmpl.label}</span>
        {tmpl.obligatorio && <span className="text-destructive ml-0.5">*</span>}
        {tmpl.ayuda && (
          <div className="text-[10px] text-muted-foreground truncate" title={tmpl.ayuda}>
            {tmpl.ayuda}
          </div>
        )}
      </div>
      <TypedValueInput
        tmpl={tmpl}
        value={spec.value}
        onChange={(v) => onUpdate({ value: v })}
      />
    </div>
  );
}

function TypedValueInput({
  tmpl, value, onChange,
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

  if (tmpl.tipo === "enum" && tmpl.enum_options && tmpl.enum_options.length > 0) {
    return (
      <Select value={value || undefined} onValueChange={onChange}>
        <SelectTrigger className="text-xs h-8">
          <SelectValue placeholder="Elegir…" />
        </SelectTrigger>
        <SelectContent>
          {tmpl.enum_options.map((opt) => (
            <SelectItem key={opt} value={opt}>{opt}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }

  if (tmpl.tipo === "bool") {
    const isYes = value.trim().toLowerCase() === "sí" || value.trim().toLowerCase() === "si"
      || value.trim().toLowerCase() === "true" || value.trim() === "1";
    return (
      <label className="flex items-center gap-2 text-xs cursor-pointer select-none">
        <input
          type="checkbox"
          checked={isYes}
          onChange={(e) => onChange(e.target.checked ? "Sí" : "")}
          className="h-4 w-4 cursor-pointer"
        />
        <span className="text-muted-foreground">{isYes ? "Sí" : "No"}</span>
      </label>
    );
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

function CustomSortableRow({
  spec, onUpdate, onRemove,
}: {
  spec: Spec;
  onUpdate: (patch: Partial<Spec>) => void;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: spec.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="flex gap-1 items-center bg-background">
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
        className="text-xs"
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
  );
}

// ── NumericValueInput (Fase B) ──────────────────────────────────────────

// ── RangoValueInput (#calidad-datos) ────────────────────────────────────
// Dos inputs separados: min y max. Si max queda vacío, se guarda como valor
// fijo (ej. "50 mm"). Si los dos están, se guarda como rango ("24-70 mm").
// La BD almacena el string final con unidad como sufijo.

function parseRango(raw: string): { min: string; max: string } {
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
  value, unidad, onChange,
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
    <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
      {unidad}
    </span>
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
      <span className="text-[11px] text-muted-foreground select-none">–</span>
      <Input
        type="number"
        inputMode="decimal"
        step="any"
        value={max}
        onChange={(e) => commit(min, e.target.value)}
        className="text-xs w-24 placeholder:text-muted-foreground/40 placeholder:italic placeholder:text-[10px]"
        placeholder="vacío si es fijo"
        aria-label="Valor máximo (vacío si es fijo)"
      />
      {!prefix && unitSpan}
    </div>
  );
}

function NumericValueInput({
  value, unidad, onChange,
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
          className={`pointer-events-none absolute inset-y-0 flex items-center text-[10px] uppercase tracking-wider text-muted-foreground ${
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
