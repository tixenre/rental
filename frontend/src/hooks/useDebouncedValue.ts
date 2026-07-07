import { useEffect, useState } from "react";

/** Devuelve `value` con retraso `delayMs` — cada cambio cancela el timer
 *  anterior (via cleanup), así solo se "asienta" un valor tras dejar de tipear. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}
