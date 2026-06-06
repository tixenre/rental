import * as React from "react";
import { cn } from "@/lib/utils";

interface ModalBackdropProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "onClick"> {
  /** Se dispara cuando el pointer-down cae directamente sobre el backdrop (no sobre el panel). */
  onClose: () => void;
}

/**
 * Backdrop robusto para modales / sheets hechos a mano — los que NO usan el
 * `Dialog` de shadcn/Radix (Radix ya maneja bien el click-outside).
 *
 * Cierra SOLO cuando el evento cae directamente sobre el overlay
 * (`e.target === e.currentTarget`), nunca cuando burbujea desde el contenido →
 * el panel va como children y **no** necesita `stopPropagation`. Usa
 * `onPointerDown` (no `onClick`) para evitar el cierre accidental: cuando un
 * elemento se re-renderiza entre `mousedown` y `mouseup`, el `click` se atribuye
 * al overlay y el modal se cerraba solo. Ver issue #761.
 *
 * Es la fuente única de esta lógica: un modal hecho a mano usa `ModalBackdrop`,
 * no recrea el patrón `onClick={onClose}` + `stopPropagation`.
 *
 * `className` define el look del overlay (z-index, fondo, layout); el
 * `fixed inset-0` ya lo pone el componente.
 */
export function ModalBackdrop({ onClose, className, children, ...props }: ModalBackdropProps) {
  return (
    <div
      className={cn("fixed inset-0", className)}
      onPointerDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      {...props}
    >
      {children}
    </div>
  );
}
