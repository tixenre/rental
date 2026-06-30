import * as React from "react";
import { Minus, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { buttonVariants } from "./button";

export interface QtyInputProps {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  /** Muestra el input con borde destructivo (ej. overstock) */
  error?: boolean;
  /** "sm" = h-7 botones (más compacto). "md" = h-9 (default). */
  size?: "sm" | "md";
  className?: string;
}

export function QtyInput({
  value,
  onChange,
  min = 1,
  max,
  error = false,
  size = "md",
  className,
}: QtyInputProps) {
  const btnH = size === "sm" ? "h-7 w-7" : "h-9 w-9";
  const inputH = size === "sm" ? "h-7 w-10" : "h-9 w-11";
  const iconSz = size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3";

  function decrement() {
    onChange(Math.max(min, value - 1));
  }
  function increment() {
    onChange(max !== undefined ? Math.min(max, value + 1) : value + 1);
  }
  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const parsed = parseInt(e.target.value, 10);
    if (!Number.isFinite(parsed)) return;
    const clamped =
      max !== undefined ? Math.min(max, Math.max(min, parsed)) : Math.max(min, parsed);
    onChange(clamped);
  }

  return (
    <div className={cn("flex items-center gap-1", className)}>
      <button
        type="button"
        aria-label="Restar uno"
        onClick={decrement}
        disabled={value <= min}
        className={cn(buttonVariants({ variant: "outline", size: "icon" }), btnH)}
      >
        <Minus className={iconSz} />
      </button>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        aria-label="Cantidad"
        onChange={handleChange}
        className={cn(
          "rounded-md border text-center font-mono text-sm tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring p-0",
          inputH,
          error
            ? "border-destructive text-destructive"
            : "border-input bg-background text-foreground",
        )}
      />
      <button
        type="button"
        aria-label="Sumar uno"
        onClick={increment}
        disabled={max !== undefined && value >= max}
        className={cn(buttonVariants({ variant: "outline", size: "icon" }), btnH)}
      >
        <Plus className={iconSz} />
      </button>
    </div>
  );
}
