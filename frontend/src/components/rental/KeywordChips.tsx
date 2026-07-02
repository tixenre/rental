import { cn } from "@/lib/utils";
import { Pill } from "@/design-system/ui/Pill";

/**
 * Chips compactos con las palabras clave editoriales del equipo.
 * Reusa el `Pill` canónico (sin `tone`, className a medida) con
 * `--area-accent-soft` — mismo patrón que el resto de `equipo.$slug.tsx`
 * (theming por área, no un color fijo; ver DECISIONES 2026-06-26).
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
  const sizes = size === "xs" ? "px-1.5 py-0.5 text-3xs" : "px-2 py-0.5 text-2xs";
  return (
    <ul className={cn("flex flex-wrap items-center gap-1", className)}>
      {list.map((k) => (
        <li key={k}>
          <Pill
            className={cn(
              "border-transparent bg-[var(--area-accent-soft)] text-ink/80 font-mono uppercase tracking-wider",
              sizes,
            )}
          >
            {k}
          </Pill>
        </li>
      ))}
    </ul>
  );
}
