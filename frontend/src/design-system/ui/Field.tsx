import { type ReactNode } from "react";

import { Label } from "@/design-system/ui/label";
import { cn } from "@/lib/utils";

/**
 * Field — molécula label + control + hint/error para forms controlados.
 *
 * Una sola forma del campo de formulario: envuelve cualquier control del DS
 * (Input/Select/Textarea) con su label, hint y mensaje de error consistentes,
 * sin recablear el markup label+control a mano en cada form. Para forms con
 * react-hook-form usar `FormField` de `ui/form`; este es para los controlados
 * con useState (la mayoría del back-office).
 */
export function Field({
  label,
  htmlFor,
  hint,
  error,
  required,
  className,
  children,
}: {
  label?: ReactNode;
  htmlFor?: string;
  /** Texto de ayuda debajo del control (se oculta si hay error). */
  hint?: ReactNode;
  /** Mensaje de error — tiene prioridad sobre el hint. */
  error?: ReactNode;
  required?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("space-y-1", className)}>
      {label && (
        <Label htmlFor={htmlFor} className="text-xs">
          {label}
          {required && <span className="ml-0.5 text-destructive">*</span>}
        </Label>
      )}
      {children}
      {error ? (
        <p className="text-2xs text-destructive">{error}</p>
      ) : hint ? (
        <p className="text-2xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}
