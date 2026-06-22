/**
 * AdminSection — header colapsable que envuelve secciones de páginas
 * largas del back-office. Estado open/closed persiste en localStorage por
 * `storageKey`.
 *
 * Diseño: NO agrega card propia — el contenido suele venir con su propio
 * <section> card. AdminSection sólo provee el botón de toggle arriba.
 * Esto evita doble-borde y permite envolver componentes existentes sin
 * tocarlos.
 *
 * Convención de keys: `<page>:<section>` (ej. `settings:descuentos`,
 * `estudio:faq`).
 */
import { useEffect, useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

export type AdminSectionProps = {
  title: string;
  /** Texto corto que aparece a la derecha cuando está cerrada. Ideal para
   *  un resumen ("3 puntos configurados", "Buffer: 12h", etc.). */
  badge?: ReactNode;
  /** Clave para persistir el estado open/closed en localStorage. */
  storageKey: string;
  /** Estado inicial cuando no hay nada en localStorage. Default abierto. */
  defaultOpen?: boolean;
  children: ReactNode;
};

export function AdminSection({
  title,
  badge,
  storageKey,
  defaultOpen = true,
  children,
}: AdminSectionProps) {
  const lsKey = `admin-section:${storageKey}`;
  const [open, setOpen] = useState(() => {
    if (typeof window === "undefined") return defaultOpen;
    try {
      const raw = window.localStorage.getItem(lsKey);
      if (raw === "1") return true;
      if (raw === "0") return false;
    } catch {
      /* ignored */
    }
    return defaultOpen;
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(lsKey, open ? "1" : "0");
    } catch {
      /* ignored — storage lleno o deshabilitado */
    }
  }, [lsKey, open]);

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-muted/30 transition text-left"
      >
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
            !open && "-rotate-90",
          )}
        />
        <span className="font-mono text-2xs uppercase tracking-[0.2em] text-muted-foreground">
          {title}
        </span>
        {badge && (
          <span className="ml-auto text-xs text-muted-foreground/80 truncate">{badge}</span>
        )}
      </button>
      {open && children}
    </div>
  );
}
