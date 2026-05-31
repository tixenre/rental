import { useNavigate } from "@tanstack/react-router";
import { ArrowRight, Minus, Plus, ShoppingBag, X } from "lucide-react";
import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { priceBreakdown } from "@/lib/pricing";
import { buildEquipoSlug } from "@/lib/equipo-slug";
import { EmptyImage } from "./EmptyImage";
import { cn } from "@/lib/utils";

/**
 * Lateral preview pane (340px) que acompaña la list view del catálogo en
 * desktop. Toggle-able: cuando está cerrado, una tab vertical "DETALLE"
 * en el borde derecho permite reabrirlo.
 *
 * Comportamiento:
 * - Sin item seleccionado → estado vacío con icono + texto guía.
 * - Con item → foto + brand/name + price block amber-soft + specs +
 *   addons + stock + footer con add-to-cart o stepper.
 *
 * Diseño: Catálogo Desktop.html sección "Preview pane (right col)".
 */
export function PreviewPane({
  item,
  open,
  onClose,
  onOpen,
  disponible,
}: {
  item: Equipment | null;
  open: boolean;
  onClose: () => void;
  onOpen: () => void;
  disponible?: number;
}) {
  if (!open) {
    return (
      <button
        type="button"
        onClick={onOpen}
        className="sticky top-[140px] z-[var(--z-sub-toolbar)] hidden lg:flex items-center justify-center gap-1.5 h-32 w-7 self-start [writing-mode:vertical-rl] rotate-180 rounded-l-md border border-r-0 border-[var(--hairline)] bg-card font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground hover:text-ink hover:border-ink transition"
        aria-label="Mostrar panel de detalle"
      >
        Detalle <ArrowRight className="h-3 w-3" />
      </button>
    );
  }

  return (
    <aside
      className="sticky top-[140px] hidden lg:flex flex-col h-[calc(100vh-140px-var(--cart-strip-h,0px))] w-[340px] shrink-0 border-l border-[var(--hairline)] bg-card overflow-hidden"
      aria-label="Panel de detalle del equipo seleccionado"
    >
      <div className="flex items-center justify-between border-b border-[var(--hairline)] px-4 py-2 shrink-0">
        <span className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted-foreground">
          Detalle
        </span>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center gap-1 rounded-full bg-ink text-amber px-2.5 py-1 font-mono text-[9px] uppercase tracking-wider hover:bg-amber hover:text-ink transition"
        >
          Ocultar <X className="h-2.5 w-2.5" />
        </button>
      </div>

      {item ? <PreviewBody item={item} disponible={disponible} /> : <PreviewEmpty />}
    </aside>
  );
}

function PreviewEmpty() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3 p-8 text-muted-foreground text-center">
      <div className="opacity-25">
        <ShoppingBag className="h-12 w-12" strokeWidth={1.2} />
      </div>
      <div className="font-sans text-[13px] leading-[1.5]">
        Hacé click en un equipo de la lista para ver su detalle, precio y agregarlo al rental.
      </div>
    </div>
  );
}

function PreviewBody({ item, disponible }: { item: Equipment; disponible?: number }) {
  const navigate = useNavigate();
  const qty = useCart((s) => s.items[item.id] ?? 0);
  const add = useCart((s) => s.add);
  const remove = useCart((s) => s.remove);
  const jornadas = useCart((s) => s.days());
  const hasDateRange = useCart((s) => !!s.startDate && !!s.endDate);

  const cap = disponible ?? item.cantidad ?? Infinity;
  const sinStock = cap <= 0;
  const price = priceBreakdown(item.pricePerDay, jornadas, 1);
  const showPeriodTotal = hasDateRange && jornadas > 1;

  const specs = (item.specsDestacados ?? []).slice(0, 6);

  return (
    <>
      <div className="flex-1 overflow-y-auto [scrollbar-width:thin] [scrollbar-color:var(--hairline)_transparent]">
        <button
          type="button"
          onClick={() => navigate({ to: "/equipo/$slug", params: { slug: buildEquipoSlug(item) } })}
          className="w-full aspect-[4/3] bg-surface border-b border-[var(--hairline)] flex items-center justify-center text-muted-foreground overflow-hidden"
          aria-label={`Abrir ficha completa de ${item.name}`}
        >
          {item.fotoUrl ? (
            <img
              src={item.fotoUrl}
              alt={item.name}
              className="h-full w-full object-contain"
              loading="lazy"
            />
          ) : (
            <EmptyImage category={item.category} brand={item.brand} />
          )}
        </button>

        <div className="p-5 flex flex-col gap-3.5">
          <div>
            <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
              {item.brand} · {item.category}
            </div>
            <h3 className="font-sans text-[22px] font-bold text-ink leading-[1.1] tracking-[-0.015em] mt-1">
              {item.name}
            </h3>
          </div>

          <div className="flex justify-between items-baseline rounded-lg border border-[color-mix(in_oklch,var(--amber)_35%,transparent)] bg-amber-soft px-3.5 py-3">
            <div>
              <div className="font-mono text-[22px] font-bold text-ink tabular-nums leading-none">
                {formatARS(item.pricePerDay)}
              </div>
              <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-muted-foreground mt-1">
                / jornada
              </div>
            </div>
            {showPeriodTotal && (
              <div className="text-right">
                <div className="font-mono text-[11px] text-muted-foreground">
                  {price.jornadas}j · total
                </div>
                <div className="font-mono text-[13px] font-bold text-ink tabular-nums mt-0.5">
                  {formatARS(price.total)}
                </div>
              </div>
            )}
          </div>

          {specs.length > 0 && (
            <div>
              <div className="font-mono text-[8px] uppercase tracking-[0.22em] text-muted-foreground mb-2">
                Detalles
              </div>
              <ul className="font-sans text-xs text-muted-foreground leading-[1.6]">
                {specs.map((s, i) => (
                  <li key={i}>
                    <span className="text-ink font-medium">{s.label}:</span> {s.value}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {disponible !== undefined && (
            <div
              className={cn(
                "font-mono text-[10px]",
                sinStock ? "text-destructive" : "text-muted-foreground",
              )}
            >
              {sinStock ? "Sin stock para las fechas elegidas" : `${disponible} disponibles`}
            </div>
          )}

          <button
            type="button"
            onClick={() =>
              navigate({ to: "/equipo/$slug", params: { slug: buildEquipoSlug(item) } })
            }
            className="inline-flex items-center gap-1.5 self-start font-mono text-[10px] uppercase tracking-wider text-muted-foreground hover:text-ink transition"
          >
            Ver ficha completa <ArrowRight className="h-3 w-3" />
          </button>
        </div>
      </div>

      <div className="border-t border-[var(--hairline)] bg-card p-3.5 shrink-0">
        {qty === 0 ? (
          <button
            type="button"
            onClick={() => !sinStock && add(item.id)}
            disabled={sinStock}
            className="w-full flex items-center justify-center gap-2 rounded-full bg-ink text-amber py-3.5 font-sans text-sm font-bold transition hover:bg-amber hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Plus className="h-4 w-4" />
            {sinStock ? "Sin stock" : "Agregar al rental"}
          </button>
        ) : (
          <div className="flex items-center justify-between rounded-full border-[1.5px] border-amber bg-amber px-2 py-1">
            <button
              type="button"
              onClick={() => remove(item.id)}
              className="grid h-9 w-9 place-items-center rounded-full text-ink hover:bg-[color-mix(in_oklch,var(--ink)_10%,var(--amber))] transition"
              aria-label="Quitar uno"
            >
              <Minus className="h-4 w-4" />
            </button>
            <div className="text-center">
              <div className="font-display text-[22px] font-black text-ink leading-none">{qty}</div>
              <div className="font-mono text-[8px] uppercase tracking-[0.15em] text-ink/70">
                {qty === 1 ? "unidad" : "unidades"}
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                if (disponible === undefined || qty < disponible) add(item.id);
              }}
              disabled={disponible !== undefined && qty >= disponible}
              className="grid h-9 w-9 place-items-center rounded-full text-ink hover:bg-[color-mix(in_oklch,var(--ink)_10%,var(--amber))] transition disabled:opacity-40 disabled:cursor-not-allowed"
              aria-label="Agregar uno"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </>
  );
}
