import { useState } from "react";
import { Share2, Check } from "lucide-react";
import { shareEquipo } from "@/lib/share";
import { type Equipment } from "@/data/equipment";
import { cn } from "@/lib/utils";

interface ShareButtonProps {
  /** Equipo a compartir (necesita id + marca + nombre para armar el slug). */
  item: Pick<Equipment, "id" | "brand" | "name">;
  size?: "sm" | "md";
  className?: string;
}

/**
 * Botón compartir — asset compartido de la librería `equipment/shared`.
 *
 * Misma silueta circular que `FavButton`, para que conviva en el overlay de la
 * card. La lógica (URL canónica + share nativo / copiar al portapapeles) vive
 * en `@/lib/share` — este componente es solo la UI + el feedback "Copiado". Es
 * el único botón de compartir-equipo de tipo icono: no recrear variantes
 * (ver docs/MEMORIA.md 2026-05-29).
 *
 * `e.stopPropagation()` evita disparar la navegación del contenedor padre.
 */
export function ShareButton({ item, size = "sm", className }: ShareButtonProps) {
  const [copied, setCopied] = useState(false);

  const btnSize = size === "md" ? "h-7 w-7" : "h-[22px] w-[22px]";
  const iconSize = size === "md" ? "h-3.5 w-3.5" : "h-3 w-3";

  return (
    <button
      type="button"
      onClick={async (e) => {
        e.stopPropagation();
        const result = await shareEquipo(item);
        if (result === "copied") {
          setCopied(true);
          setTimeout(() => setCopied(false), 1800);
        }
      }}
      aria-label="Compartir"
      className={cn(
        "grid place-items-center rounded-full border bg-background/80 backdrop-blur-sm transition-colors",
        copied ? "border-amber/40 text-ink" : "hairline text-muted-foreground hover:text-ink",
        btnSize,
        className,
      )}
    >
      {copied ? <Check className={iconSize} /> : <Share2 className={iconSize} />}
    </button>
  );
}
