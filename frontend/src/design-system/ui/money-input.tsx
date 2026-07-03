import * as React from "react";
import { useState } from "react";

import { formatARS } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Input } from "./input";

/**
 * MoneyInput — input numérico que se ve formateado como plata ("$ 791.100")
 * cuando no tiene foco, y como número crudo (editable sin puntos ni signo)
 * mientras se edita. Solo visual — el `value`/`onChange` siempre son el
 * número crudo, el usuario nunca tiene que tipear separadores.
 *
 * El formato ("$ X.XXX", es-AR, sin decimales) sale de `formatARS` — la
 * misma fuente única que usa toda la plata del back-office — no se le
 * pregunta al backend: es una regla de presentación fija, no un cálculo
 * (la distinción que ya hace "el front no calcula plata", 2026-06-29).
 */
export function MoneyInput({
  value,
  onChange,
  min = 0,
  max,
  step = 100,
  className,
  ariaLabel,
}: {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  className?: string;
  ariaLabel?: string;
}) {
  const [focused, setFocused] = useState(false);

  return (
    <Input
      type={focused ? "number" : "text"}
      inputMode="numeric"
      min={min}
      max={max}
      step={step}
      value={focused ? value : formatARS(value)}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      onChange={(e) => {
        if (!focused) return;
        const n = Number(e.target.value) || 0;
        const clamped = Math.max(min, max != null ? Math.min(max, n) : n);
        onChange(clamped);
      }}
      className={cn("tabular-nums", className)}
      aria-label={ariaLabel}
    />
  );
}
