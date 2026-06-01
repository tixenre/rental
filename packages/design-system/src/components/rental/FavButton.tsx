import { Heart } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * FavButton — botón de favorito para EquipmentCard y ficha de equipo.
 *
 * Conectar con el hook `useFavoritos()` de `src/hooks/useFavoritos.ts`.
 * El estado de isFav debe venir del hook; este componente es puro/presentacional.
 *
 * Comportamiento visual:
 *   - rest:    corazón outline, muted. Se oculta con opacity-0 en la card;
 *              group-hover de la card lo revela.
 *   - hover:   corazón outline, ink.
 *   - fav=true: fill amber + stroke amber. Siempre visible (no se oculta).
 *   - active:  scale(0.93) 120ms — press state firma.
 *
 * Source visual: `preview/components-favbutton.html`
 */
export interface FavButtonProps {
  isFav: boolean;
  onToggle: () => void;
  /** sm → 28px (sobre foto en card). md → 36px (ficha de equipo). */
  size?: "sm" | "md";
  className?: string;
}

export function FavButton({ isFav, onToggle, size = "sm", className }: FavButtonProps) {
  return (
    <button
      type="button"
      aria-label={isFav ? "Quitar de favoritos" : "Agregar a favoritos"}
      aria-pressed={isFav}
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      className={cn(
        "grid place-items-center rounded-full",
        "border border-hairline bg-surface-elevated/80 backdrop-blur-sm",
        "transition-all duration-[var(--duration-fast)]",
        "hover:border-ink/20",
        "active:scale-[0.93]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-1",
        size === "sm" ? "h-7 w-7" : "h-9 w-9",
        className,
      )}
    >
      <Heart
        className={cn(
          "transition-colors duration-[var(--duration-base)]",
          size === "sm" ? "h-3.5 w-3.5" : "h-4 w-4",
          isFav
            ? "fill-amber stroke-amber"
            : "fill-transparent stroke-muted-foreground group-hover:stroke-ink",
        )}
      />
    </button>
  );
}
