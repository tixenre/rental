import { Heart } from "lucide-react";
import { useFavoritos } from "@/hooks/useFavoritos";
import { cn } from "@/lib/utils";

interface FavButtonProps {
  /** ID del equipo (se normaliza a string para el store de favoritos). */
  itemId: string;
  size?: "sm" | "md";
  className?: string;
}

/**
 * Botón favorito — asset compartido de la librería `equipment/shared`.
 *
 * Cableado a `useFavoritos()` (localStorage + sync al backend cuando el cliente
 * está logueado). El estado persiste entre navegaciones y sesiones. Es el único
 * botón de favorito de la web: no recrear variantes (ver docs/MEMORIA.md
 * 2026-05-29).
 *
 * `e.stopPropagation()` evita disparar el toggle del expand o la navegación del
 * contenedor padre.
 */
export function FavButton({ itemId, size = "sm", className }: FavButtonProps) {
  const fav = useFavoritos();
  const id = String(itemId);
  const isFav = fav.has(id);

  const btnSize = size === "md" ? "h-7 w-7" : "h-[22px] w-[22px]";
  const iconSize = size === "md" ? "h-3.5 w-3.5" : "h-3 w-3";

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        fav.toggle(id);
      }}
      aria-label={isFav ? "Quitar de favoritos" : "Guardar en favoritos"}
      aria-pressed={isFav}
      className={cn(
        // `hit-area-44` (utilitario único del DS): área táctil ≥44px sin agrandar
        // el visual (queda chico e intencional sobre el thumb). Antes vivía como
        // clases `before:` inline acá — ahora es la fuente única de hit-area.
        "hit-area-44 grid place-items-center rounded-full border bg-background/80 backdrop-blur-sm transition-colors",
        isFav
          ? "border-destructive/30 text-destructive"
          : "hairline text-muted-foreground hover:text-destructive",
        btnSize,
        className,
      )}
    >
      <Heart className={cn(iconSize, isFav && "fill-current")} />
    </button>
  );
}
