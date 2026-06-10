import { type MouseEvent } from "react";
import { Minus, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

interface StepperPillProps {
  qty: number;
  /** Recibe el evento (opcional) — habilita usos como fly-to-cart desde el botón. */
  onIncrement: (e: MouseEvent<HTMLButtonElement>) => void;
  onDecrement: (e: MouseEvent<HTMLButtonElement>) => void;
  /**
   * Tamaño VISUAL de los botones (el área táctil es ≥44px en todos — en
   * sm/md se extiende con un pseudo-elemento, ver `hitArea`):
   * - `sm` = 28px (grid card / lista desktop)
   * - `md` = 30px (mobile)
   * - `lg` = 44px (CartDrawer / ficha — tap target HIG nativo)
   */
  size?: "sm" | "md" | "lg";
  maxReached?: boolean;
  className?: string;
}

/**
 * Stepper pill hairline — asset compartido de la librería `equipment/shared`.
 *
 * Es el ÚNICO stepper de cantidad de la web: se usa en las tres vistas del
 * catálogo (grid card, lista desktop, row mobile) y en el CartDrawer. No
 * crear variantes ad-hoc (ver decisión en docs/MEMORIA.md 2026-05-29).
 *
 * Fondo transparente, borde hairline, botones con `hover:bg-surface`. El amber
 * NO va en el stepper — solo en el borde del *contenedor de la card* cuando el
 * item está in-cart.
 */
export function StepperPill({
  qty,
  onIncrement,
  onDecrement,
  size = "sm",
  maxReached = false,
  className,
}: StepperPillProps) {
  const btnCls = size === "lg" ? "h-11 w-11" : size === "md" ? "h-[30px] w-[30px]" : "h-7 w-7";

  // Área táctil ≥44px sin agrandar el visual (HIG, MEMORIA 2026-06-05): en
  // sm/md cada botón extiende su hit-area con un pseudo-elemento hacia afuera
  // (vertical + flanco externo). No se expande hacia adentro para que la zona
  // del número no dispare un botón por error.
  const hitArea =
    size === "lg"
      ? { dec: "", inc: "" }
      : size === "md"
        ? {
            dec: "relative before:absolute before:-inset-y-[7px] before:-left-[14px] before:right-0",
            inc: "relative before:absolute before:-inset-y-[7px] before:-right-[14px] before:left-0",
          }
        : {
            dec: "relative before:absolute before:-inset-y-2 before:-left-4 before:right-0",
            inc: "relative before:absolute before:-inset-y-2 before:-right-4 before:left-0",
          };

  return (
    <div
      className={cn(
        "inline-flex shrink-0 items-center rounded-full border hairline bg-background",
        className,
      )}
    >
      <button
        type="button"
        onClick={onDecrement}
        aria-label="Quitar uno"
        className={cn(
          "grid place-items-center rounded-full text-ink transition-colors hover:bg-surface active:bg-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-amber",
          btnCls,
          hitArea.dec,
        )}
      >
        <Minus className="h-3 w-3" />
      </button>

      <span className="min-w-[20px] text-center font-mono text-xs font-semibold tabular-nums text-ink">
        {qty}
      </span>

      <button
        type="button"
        onClick={onIncrement}
        disabled={maxReached}
        aria-label="Agregar uno"
        className={cn(
          "grid place-items-center rounded-full text-ink transition-colors hover:bg-surface active:bg-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-amber disabled:cursor-not-allowed disabled:opacity-40",
          btnCls,
          hitArea.inc,
        )}
      >
        <Plus className="h-3 w-3" />
      </button>
    </div>
  );
}
