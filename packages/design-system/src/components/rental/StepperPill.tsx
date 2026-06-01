import { Minus, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * StepperPill — el único stepper de cantidad de la app.
 *
 * Usado en EquipmentCard (catálogo), CartDrawer (items), y en cualquier
 * pantalla donde el usuario ajuste cantidades de equipo.
 *
 * REGLA: no reinventar este componente. Si necesitás un contador, usá
 * este. Si falta un prop, extendelo acá — no crees una variante paralela.
 *
 * Source visual: `preview/components-badges-stepper.html`
 * Source tokens: `docs/DESIGN_SYSTEM.md` → Radii, Spacing, Motion
 *
 * Sizes:
 *   - sm  → 28px height. EquipmentCard en grid.
 *   - md  → 36px height. Default. Pantallas de detalle.
 *   - lg  → 44px height. CartDrawer footer, confirmación.
 */

type StepperSize = "sm" | "md" | "lg";

const SIZE = {
  sm: { pill: "h-7 gap-0.5 px-0.5", btn: "h-5 w-5", count: "text-xs min-w-[18px]" },
  md: { pill: "h-9 gap-1   px-1", btn: "h-6 w-6", count: "text-sm min-w-[22px]" },
  lg: { pill: "h-11 gap-1.5 px-1.5", btn: "h-7 w-7", count: "text-base min-w-[26px]" },
} satisfies Record<StepperSize, { pill: string; btn: string; count: string }>;

export interface StepperPillProps {
  value: number;
  onIncrement: () => void;
  onDecrement: () => void;
  /** Mínimo inclusive (default 0). Al llegar al mínimo, el botón − se deshabilita. */
  min?: number;
  /** Máximo inclusive. Sin max, el + nunca se deshabilita. */
  max?: number;
  size?: StepperSize;
  className?: string;
}

export function StepperPill({
  value,
  onIncrement,
  onDecrement,
  min = 0,
  max,
  size = "md",
  className,
}: StepperPillProps) {
  const s = SIZE[size];
  const atMin = value <= min;
  const atMax = max !== undefined && value >= max;

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border border-hairline bg-surface-elevated",
        s.pill,
        className,
      )}
    >
      <button
        type="button"
        aria-label="Restar uno"
        disabled={atMin}
        onClick={onDecrement}
        className={cn(
          "grid place-items-center rounded-full bg-surface text-ink",
          "transition-all duration-[var(--duration-fast)]",
          "hover:bg-ink hover:text-background",
          "active:scale-[0.97]",
          "disabled:opacity-30 disabled:pointer-events-none",
          s.btn,
        )}
      >
        <Minus strokeWidth={2.5} className="h-3 w-3" />
      </button>

      <span
        className={cn(
          "text-center font-mono font-semibold tabular-nums text-ink select-none",
          s.count,
        )}
      >
        {value}
      </span>

      <button
        type="button"
        aria-label="Sumar uno"
        disabled={atMax}
        onClick={onIncrement}
        className={cn(
          "grid place-items-center rounded-full bg-surface text-ink",
          "transition-all duration-[var(--duration-fast)]",
          "hover:bg-ink hover:text-background",
          "active:scale-[0.97]",
          "disabled:opacity-30 disabled:pointer-events-none",
          s.btn,
        )}
      >
        <Plus strokeWidth={2.5} className="h-3 w-3" />
      </button>
    </div>
  );
}
