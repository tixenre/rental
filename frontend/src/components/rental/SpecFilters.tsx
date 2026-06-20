/**
 * Filtros por specs estructuradas — chips dinámicos.
 *
 * Render una sección por cada spec filtrable (descubierta del dataset).
 * Cada sección es un grupo de chips horizontal con los valores únicos.
 * Click toggle: si el valor ya estaba seleccionado, lo limpia.
 *
 * Solo se renderiza si hay specs disponibles (>= 1 spec con 2+ valores).
 *
 * Fase H del refactor de specs.
 */

import { cn } from "@/lib/utils";

import type { SpecFilterDef } from "@/hooks/useEquipos";

export function SpecFilters({
  filterableSpecs,
  selected,
  onChange,
  layout = "stacked",
}: {
  filterableSpecs: SpecFilterDef[];
  selected: Record<string, string>;
  onChange: (key: string, value: string | null) => void;
  /** "stacked" = label arriba + chips abajo (mobile sheet).
   *  "inline" = todo en una fila (desktop sticky bar). */
  layout?: "stacked" | "inline";
}) {
  if (filterableSpecs.length === 0) return null;

  return (
    <div
      className={cn(
        "flex gap-3",
        layout === "stacked" ? "flex-col" : "flex-row flex-wrap items-start",
      )}
    >
      {filterableSpecs.map((spec) => (
        <div
          key={spec.key}
          className={cn("flex gap-1.5", layout === "stacked" ? "flex-col" : "flex-col min-w-0")}
        >
          <label className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground font-medium">
            {spec.label}
          </label>
          <div className="flex flex-wrap gap-1">
            {spec.values.map((value) => {
              const isActive = selected[spec.key] === value;
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => onChange(spec.key, isActive ? null : value)}
                  className={cn(
                    "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] transition",
                    isActive
                      ? "border-amber bg-amber-soft text-ink"
                      : "border-ink/15 bg-background text-muted-foreground hover:border-ink/30 hover:text-ink",
                  )}
                  aria-pressed={isActive}
                >
                  {value}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
