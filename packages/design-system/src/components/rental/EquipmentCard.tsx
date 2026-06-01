import { cn } from "@/lib/utils";
import { PriceBlock } from "@/components/kit/PriceBlock";
import { StepperPill } from "./StepperPill";
import { FavButton } from "./FavButton";

/**
 * EquipmentCard — tarjeta del catálogo de alquiler.
 *
 * Layout: foto 1:1 → body con brand eyebrow + nombre + PriceBlock + StepperPill.
 *
 * Estados:
 *   - default:    border hairline, shadow-sm
 *   - inCart:     border amber/50, shadow-md, ring amber/60 sobre la foto
 *   - outOfStock: opacity-50, overlay rojo sobre foto, sin stepper
 *   - hover:      translateY(-2px) + shadow-md (solo si hay stock)
 *
 * Uso con FlyToCartLayer: al ejecutar onIncrement, pasá el
 * `getBoundingClientRect()` de la foto (ref `photoRef`) como `from`
 * al layer de animación.
 *
 * Source visual: `preview/components-equipment-card.html`
 * Source tokens: `docs/DESIGN_SYSTEM.md` → Cards, Motion
 */

export interface EquipmentCardItem {
  id: string;
  brand: string;
  name: string;
  category: string;
  pricePerDay: number;
  photoUrl?: string;
  inStock: boolean;
  /** Extras incluidos — se muestran como AddonPills en la ficha, no en la card. */
  includes?: string[];
  destacado?: boolean;
}

export interface EquipmentCardProps {
  item: EquipmentCardItem;
  /** Cantidad actual en el carrito (0 = fuera del carrito). */
  qty: number;
  /** Jornadas seleccionadas. Sin valor, PriceBlock muestra precio/día. */
  jornadas?: number;
  isFav?: boolean;
  onIncrement: () => void;
  onDecrement: () => void;
  onFavToggle: () => void;
  /** Navegar a la ficha del equipo. */
  onCardClick?: () => void;
  className?: string;
}

export function EquipmentCard({
  item,
  qty,
  jornadas,
  isFav = false,
  onIncrement,
  onDecrement,
  onFavToggle,
  onCardClick,
  className,
}: EquipmentCardProps) {
  const inCart = qty > 0;
  const outOfStock = !item.inStock;

  return (
    <article
      role={onCardClick ? "button" : undefined}
      tabIndex={onCardClick ? 0 : undefined}
      onClick={onCardClick}
      onKeyDown={onCardClick ? (e) => e.key === "Enter" && onCardClick() : undefined}
      className={cn(
        "group relative flex flex-col rounded-lg border bg-surface-elevated",
        "transition-all duration-[var(--duration-base)]",
        inCart
          ? "border-amber/50 shadow-[var(--shadow-md)]"
          : "border-hairline shadow-[var(--shadow-sm)]",
        !outOfStock && "hover:-translate-y-0.5 hover:shadow-[var(--shadow-md)]",
        outOfStock && "opacity-50",
        onCardClick && "cursor-pointer",
        className,
      )}
    >
      {/* ── Foto 1:1 ── */}
      <div className="relative aspect-square overflow-hidden rounded-t-lg bg-surface">
        {item.photoUrl ? (
          <img
            src={item.photoUrl}
            alt={item.name}
            className="h-full w-full object-cover"
            draggable={false}
          />
        ) : (
          /* TODO: placeholder imagen equipo */
          <div className="flex h-full items-center justify-center">
            <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground/40">
              foto equipo
            </span>
          </div>
        )}

        {/* FavButton — aparece en hover de la card */}
        <FavButton
          isFav={isFav}
          onToggle={onFavToggle}
          size="sm"
          className={cn(
            "absolute right-2 top-2",
            "transition-opacity duration-[var(--duration-base)]",
            isFav ? "opacity-100" : "opacity-0 group-hover:opacity-100",
          )}
        />

        {/* Sin stock overlay */}
        {outOfStock && (
          <div className="absolute inset-0 flex items-center justify-center bg-destructive/10">
            <span className="rounded-full bg-destructive/90 px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-white">
              Sin stock
            </span>
          </div>
        )}

        {/* In-cart ring — aro interno sobre la foto */}
        {inCart && (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 rounded-t-lg ring-2 ring-inset ring-amber/60"
          />
        )}
      </div>

      {/* ── Body ── */}
      <div className="flex flex-1 flex-col gap-2 p-3">
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
            {item.brand}
          </p>
          <p className="mt-0.5 text-sm font-semibold leading-tight text-ink">{item.name}</p>
        </div>

        <div className="mt-auto flex items-end justify-between gap-2">
          <PriceBlock
            pricePerDay={item.pricePerDay}
            jornadas={jornadas}
            align="left"
            className="flex-1 min-w-0"
          />

          {!outOfStock && (
            /* stopPropagation para que el stepper no dispare onCardClick */
            <div onClick={(e) => e.stopPropagation()}>
              <StepperPill
                value={qty}
                onIncrement={onIncrement}
                onDecrement={onDecrement}
                min={0}
                size="sm"
              />
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
