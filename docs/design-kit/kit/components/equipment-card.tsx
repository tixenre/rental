import { useState } from "react";
import { Check, Minus, Plus, Sparkles } from "lucide-react";
import type { Equipment } from "../types/equipment";
import { formatARS as defaultFormatARS } from "../lib/format";
import { cn } from "./lib/cn";

export type { Equipment };

/**
 * EquipmentCard — la card 4:5 que arma la grilla del catálogo público.
 *
 * Versión presentacional: recibe `qty` + callbacks por props (sin cart store)
 * para que sea fácil de reusar. Si vas a integrarla con Zustand u otro store,
 * envolvela en un container que lea/escriba allí.
 *
 * Anatomía:
 *   ┌──────────────────────┐
 *   │  ┌───────────────┐   │
 *   │  │  [foto, 1:1]  │   │  ← 4/5 del alto
 *   │  │  badges + qty │   │
 *   │  └───────────────┘   │
 *   │  BRAND · name        │  ← 1/5 del alto
 *   │  $ 12.500 /jornada + │
 *   └──────────────────────┘
 *
 * Estados visuales:
 *   - default        hairline border, hover → border-foreground/20
 *   - selected       amber border + halo amber. badge ✓ en photo.
 *   - sinStock       opacity 50% + overlay "Sin stock"
 *
 * @example
 *   <EquipmentCard
 *     item={{ id: "1", name: "Sony A7S III", brand: "SONY", category: "Cámaras",
 *             pricePerDay: 24500, fotoUrl: "/equipos/a7s3.webp",
 *             cantidad: 4, isNew: true }}
 *     qty={0}
 *     onAdd={(id) => store.add(id)}
 *     onRemove={(id) => store.remove(id)}
 *     onOpen={(id) => navigate(`/equipo/${id}`)}
 *   />
 */

export interface EquipmentCardProps {
  item: Equipment;
  /** Cantidad seleccionada en el carrito. 0 = no seleccionado. */
  qty: number;
  /** Disponible en las fechas elegidas. undefined = sin fechas (muestra stock total). */
  disponible?: number;
  /** Ancho fijo en px para uso dentro de carrusel; si no, ocupa la celda. */
  width?: number;
  /** Locale opcional para formateo de precio. Default: es-AR / ARS. */
  formatPrice?: (price: number) => string;
  onAdd: (id: string) => void;
  onRemove: (id: string) => void;
  /** Click sobre la foto o el nombre → abrir ficha. */
  onOpen?: (id: string) => void;
  className?: string;
}

export function EquipmentCard({
  item,
  qty,
  disponible,
  width,
  formatPrice = defaultFormatARS,
  onAdd,
  onRemove,
  onOpen,
  className,
}: EquipmentCardProps) {
  const [imgFailed, setImgFailed] = useState(false);

  const cap = disponible ?? item.cantidad;
  const sinStock = cap <= 0;
  const stockBajo = !sinStock && cap > 0 && cap <= 2;
  const reachedMax = qty >= cap;
  const selected = qty > 0;

  const initials = item.name
    .split(/\s+/)
    .slice(1, 3)
    .map((w) => w[0])
    .join("")
    .toUpperCase() || "—";

  return (
    <article
      style={width ? { width } : undefined}
      className={cn(
        "group relative flex shrink-0 flex-col overflow-hidden rounded-lg border bg-surface aspect-[4/5] transition-all",
        selected
          ? "border-amber/60 shadow-[0_0_0_1px_var(--amber)]"
          : sinStock
            ? "border-hairline opacity-50"
            : "border-hairline hover:border-foreground/20",
        className,
      )}
    >
      <button
        type="button"
        onClick={() => onOpen?.(item.id)}
        aria-label={`Ver detalle de ${item.name}`}
        className="relative block aspect-square w-full shrink-0 overflow-hidden bg-white text-left"
      >
        {item.fotoUrl && !imgFailed ? (
          <img
            src={item.fotoUrl}
            alt={item.name}
            onError={() => setImgFailed(true)}
            className="h-full w-full object-contain p-3 transition group-hover:scale-[1.02]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-amber-soft via-surface to-amber-soft">
            <span className="font-display text-3xl font-black text-ink/30">
              {initials}
            </span>
          </div>
        )}

        {item.isNew && (
          <div className="absolute left-2 top-2 flex items-center gap-1 rounded-full bg-ink px-2 py-0.5 font-mono text-[9px] uppercase tracking-widest text-amber">
            <Sparkles className="h-2.5 w-2.5" /> nuevo
          </div>
        )}
        {item.destacado && !selected && (
          <div className="absolute right-2 top-2 rounded-full bg-amber/90 px-2 py-0.5 font-mono text-[9px] uppercase tracking-widest text-ink shadow-sm">
            ★ destacado
          </div>
        )}
        {selected && (
          <div className="absolute right-2 top-2 grid h-6 w-6 place-items-center rounded-full bg-amber text-ink">
            <Check className="h-3.5 w-3.5" strokeWidth={3} />
          </div>
        )}
        {sinStock && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/70">
            <span className="rounded-full border border-hairline bg-background px-3 py-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Sin stock
            </span>
          </div>
        )}
      </button>

      <div className="flex min-h-0 flex-1 items-center gap-2 px-2.5 py-1.5">
        <button
          type="button"
          onClick={() => onOpen?.(item.id)}
          className="flex min-w-0 flex-1 flex-col text-left"
        >
          <div className="truncate font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground">
            {item.brand}
          </div>
          <div className="truncate font-sans text-sm font-semibold leading-tight tracking-tight text-ink hover:underline">
            {item.name}
          </div>
          <div className="flex items-baseline gap-1.5 leading-none">
            <span className="font-sans text-sm font-semibold tabular text-ink">
              {formatPrice(item.pricePerDay)}
            </span>
            <span className="font-mono text-[8px] uppercase tracking-widest text-muted-foreground">
              /jornada
            </span>
            {disponible !== undefined && (
              <span
                className={cn(
                  "ml-auto font-mono text-[9px] uppercase tracking-widest tabular",
                  sinStock
                    ? "text-destructive"
                    : stockBajo
                      ? "text-naranja"
                      : "text-muted-foreground",
                )}
              >
                {sinStock ? "—" : `${cap} disp.`}
              </span>
            )}
          </div>
        </button>

        {qty === 0 ? (
          <button
            onClick={() => !sinStock && onAdd(item.id)}
            disabled={sinStock}
            aria-label="Agregar al carrito"
            className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-hairline transition hover:border-amber hover:bg-amber hover:text-ink active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 sm:h-9 sm:w-9"
          >
            <Plus className="h-4 w-4" />
          </button>
        ) : (
          <div className="flex shrink-0 items-center gap-0.5 rounded-md border border-amber/40 bg-amber-soft p-0.5">
            <button
              onClick={() => onRemove(item.id)}
              className="grid h-9 w-9 place-items-center rounded text-amber hover:bg-amber/20"
              aria-label="Quitar uno"
            >
              <Minus className="h-4 w-4" />
            </button>
            <span className="w-5 text-center font-sans text-sm tabular">{qty}</span>
            <button
              onClick={() => !reachedMax && onAdd(item.id)}
              disabled={reachedMax}
              className="grid h-9 w-9 place-items-center rounded text-amber hover:bg-amber/20 disabled:cursor-not-allowed disabled:opacity-40"
              aria-label="Sumar uno"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </article>
  );
}
