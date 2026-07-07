import { forwardRef, useEffect, useRef, type ComponentProps } from "react";
import { Search, X } from "lucide-react";
import { Input } from "./input";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { cn } from "@/lib/utils";

type SearchInputProps = Omit<ComponentProps<typeof Input>, "value" | "onChange"> & {
  value: string;
  onValueChange: (value: string) => void;
  /** Junto con `onDebouncedChange`: dispara ese callback `debounceMs` después
   *  del último cambio — para drivear una query sin una por cada tecla. El
   *  valor visible del input (`value`/`onValueChange`) sigue siendo instantáneo. */
  debounceMs?: number;
  onDebouncedChange?: (value: string) => void;
  /** Botón "×" para vaciar, visible solo cuando hay texto. */
  clearable?: boolean;
  /** className del `<div>` contenedor (ej. `flex-1` en una toolbar) — `className`
   *  a secas sigue yendo al `<input>` (como en `Input`). */
  wrapperClassName?: string;
};

/**
 * SearchInput — primitivo único de búsqueda: lupa a la izquierda + `Input` del
 * DS + botón de limpiar opcional. Consolida las 9 copias que habían aparecido
 * en el repo con variantes de padding/tamaño de icono/posición ligeramente
 * distintas de lo mismo. Hereda `text-base md:text-sm` de `Input` (floor iOS
 * por construcción, sin que cada consumidor lo reagregue).
 */
export const SearchInput = forwardRef<HTMLInputElement, SearchInputProps>(function SearchInput(
  {
    value,
    onValueChange,
    debounceMs,
    onDebouncedChange,
    clearable = false,
    className,
    wrapperClassName,
    ...props
  },
  ref,
) {
  const debounced = useDebouncedValue(value, debounceMs ?? 0);
  const onDebouncedChangeRef = useRef(onDebouncedChange);
  onDebouncedChangeRef.current = onDebouncedChange;
  useEffect(() => {
    onDebouncedChangeRef.current?.(debounced);
  }, [debounced]);

  return (
    <div className={cn("relative", wrapperClassName)}>
      <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
      <Input
        ref={ref}
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        className={cn("pl-9", clearable && "pr-9", className)}
        {...props}
      />
      {clearable && value && (
        <button
          type="button"
          onClick={() => onValueChange("")}
          aria-label="Limpiar búsqueda"
          className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-ink"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
});
SearchInput.displayName = "SearchInput";
