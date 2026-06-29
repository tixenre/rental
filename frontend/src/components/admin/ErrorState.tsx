import { type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/design-system/ui/button";

/**
 * ErrorState — estado de error canónico del back-office.
 *
 * Molde de `EmptyState` con tono destructive. Resuelve el problema sistémico
 * "cada pantalla pinta {e.message} crudo": loguea el mensaje técnico a la consola
 * y muestra copy genérico + Reintentar. Una sola forma del error en todo el admin.
 *
 * No lo uses suelto si podés usar `<QueryState>` (que ya lo cablea al loading/empty).
 */
export function ErrorState({
  title = "No se pudo cargar",
  sub = "Hubo un error al traer los datos. Probá de nuevo.",
  error,
  onRetry,
  className,
  children,
}: {
  title?: string;
  sub?: string;
  /** Error técnico — se loguea a consola, NO se pinta en la UI. */
  error?: unknown;
  onRetry?: () => void;
  className?: string;
  children?: ReactNode;
}) {
  if (error) {
    // Loguear el mensaje técnico para debugging, sin filtrarlo a la pantalla.
    console.error("[admin] ErrorState:", error);
  }
  return (
    <div
      className={cn("flex flex-col items-center justify-center gap-4 py-12 text-center", className)}
    >
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <div>
        <div className="font-display text-xl font-black text-ink">{title}</div>
        <p className="mt-1 max-w-xs text-sm text-muted-foreground">{sub}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Reintentar
        </Button>
      )}
      {children}
    </div>
  );
}
