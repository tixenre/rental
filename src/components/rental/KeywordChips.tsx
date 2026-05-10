import { cn } from "@/lib/utils";

/**
 * Chips compactos con las palabras clave editoriales del equipo.
 * Estilo distinto a las categorías: pill amber suave, sin borde.
 */
export function KeywordChips({
  keywords,
  max,
  size = "sm",
  className,
}: {
  keywords?: string[];
  max?: number;
  size?: "sm" | "xs";
  className?: string;
}) {
  if (!keywords || keywords.length === 0) return null;
  const list = max ? keywords.slice(0, max) : keywords;
  const sizes =
    size === "xs"
      ? "px-1.5 py-0.5 text-[9px]"
      : "px-2 py-0.5 text-[10px]";
  return (
    <ul className={cn("flex flex-wrap items-center gap-1", className)}>
      {list.map((k) => (
        <li
          key={k}
          className={cn(
            "inline-flex items-center rounded-full bg-amber-soft text-ink/80 font-mono uppercase tracking-wider",
            sizes,
          )}
        >
          {k}
        </li>
      ))}
    </ul>
  );
}
