import { type Equipment } from "@/data/equipment";

interface SpecsGridProps {
  item: Equipment;
  /** Cuántas specs mostrar. Default 6. */
  max?: number;
}

/**
 * SpecsGrid — grid de specs clave de un equipo.
 *
 * Usa las specs marcadas `destacado` en el registry (vienen en `specsRaw`).
 * Si el equipo no tiene destacadas, cae a las primeras por prioridad.
 * Reutilizable en la ficha, cards expandidas, flyouts, etc.
 */
export function SpecsGrid({ item, max = 6 }: SpecsGridProps) {
  const specs = item.specs ?? [];

  const destLabels = new Set(
    Object.values((item.specsRaw ?? {}) as Record<string, { label?: string; destacado?: boolean }>)
      .filter((s) => s?.destacado)
      .map((s) => s.label),
  );

  const curated = specs.filter((s) => destLabels.has(s.label));
  const destacados = (curated.length > 0 ? curated : specs).slice(0, max);

  if (destacados.length === 0) return null;

  return (
    <section className="space-y-2">
      <h2 className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        Specs clave
      </h2>
      <dl className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {destacados.map((s, i) => (
          <div
            key={`${s.label}-${i}`}
            className="rounded-lg border hairline bg-surface px-3 py-2.5"
          >
            <dt className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
              {s.label}
            </dt>
            <dd className="mt-1 font-mono text-lg font-semibold tabular-nums text-ink leading-tight">
              {s.value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
