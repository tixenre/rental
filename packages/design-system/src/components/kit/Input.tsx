import * as React from "react";
import { Search } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Input — campo de texto branded del kit Rambla.
 *
 * Variante del Input shadcn con ring amber-soft y borde hairline default. Convive con
 * `src/components/ui/input.tsx`; los nuevos forms pueden elegir.
 */
export const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        ref={ref}
        type={type}
        className={cn(
          "flex h-9 w-full rounded-md border border-hairline bg-surface-elevated px-3 py-1 font-sans text-sm text-ink shadow-sm transition-colors",
          "placeholder:text-muted-foreground",
          "focus-visible:outline-none focus-visible:border-amber focus-visible:ring-2 focus-visible:ring-amber-soft",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-ink",
          className,
        )}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

/**
 * SearchInput — variante pill con icono lupa a la izquierda.
 * Borde más grueso (2px) y radius-full. Usada en sub-toolbar del catálogo.
 */
export const SearchInput = React.forwardRef<
  HTMLInputElement,
  React.ComponentProps<"input"> & { iconClassName?: string }
>(({ className, iconClassName, ...props }, ref) => {
  return (
    <div className="relative w-full">
      <Search
        className={cn(
          "pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground",
          iconClassName,
        )}
        strokeWidth={2.2}
      />
      <input
        ref={ref}
        type="search"
        className={cn(
          "flex h-10 w-full rounded-full border-2 border-hairline bg-surface-elevated pl-9 pr-4 font-sans text-sm text-ink shadow-sm transition-colors",
          "placeholder:text-muted-foreground",
          "focus-visible:outline-none focus-visible:border-amber focus-visible:ring-2 focus-visible:ring-amber-soft",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
    </div>
  );
});
SearchInput.displayName = "SearchInput";

/**
 * FieldLabel — eyebrow mono que va arriba de cada input. Tracking 0.22em,
 * uppercase, font-mono 9px. Muted-foreground por default.
 */
export function FieldLabel({
  children,
  htmlFor,
  className,
}: {
  children: React.ReactNode;
  htmlFor?: string;
  className?: string;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className={cn(
        "font-mono text-[9px] font-medium uppercase tracking-[0.22em] text-muted-foreground",
        className,
      )}
    >
      {children}
    </label>
  );
}
