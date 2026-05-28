import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "./lib/cn";

/**
 * Rambla Button — el botón con la jugada de marca:
 * hover invierte ink ⇄ amber (la "reverse" característica).
 *
 * Variantes:
 *   - primary       (default) ink → amber on hover. CTA principal.
 *   - secondary     surface + hairline → amber-soft on hover. Acciones lado a lado.
 *   - ghost         transparent → amber-soft on hover. Acciones inline / chrome.
 *   - destructive   destructive bg. Borrar / cancelar.
 *   - amber         siempre amber (no se invierte). Para CTAs sobre fondos oscuros.
 *
 * Tamaños: sm · md (default) · lg · icon.
 * Formas: rounded (default · radius-md) · pill (rounded-full, para CTAs).
 *
 * @example
 *   <Button>Reservar</Button>
 *   <Button variant="secondary" shape="pill">Ver carrito</Button>
 *   <Button variant="ghost" size="icon"><Search /></Button>
 *   <Button asChild><a href="/estudio">Conocé el Estudio</a></Button>
 */
export const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap",
    "font-sans text-sm font-medium",
    "transition-colors duration-150",
    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
    "disabled:pointer-events-none disabled:opacity-50",
    "[&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        primary:
          "bg-ink text-background shadow-sm hover:bg-amber hover:text-ink",
        secondary:
          "bg-surface text-ink border border-hairline hover:bg-amber-soft hover:border-ink/30",
        ghost:
          "bg-transparent text-ink hover:bg-amber-soft",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        amber:
          "bg-amber text-ink shadow-sm hover:bg-amber-hot",
      },
      size: {
        sm:   "h-8 px-3 text-xs",
        md:   "h-9 px-4",
        lg:   "h-11 px-6 text-base",
        icon: "h-9 w-9",
      },
      shape: {
        rounded: "rounded-md",
        pill:    "rounded-full",
      },
    },
    defaultVariants: {
      variant: "primary",
      size:    "md",
      shape:   "rounded",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, shape, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size, shape, className }))}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
