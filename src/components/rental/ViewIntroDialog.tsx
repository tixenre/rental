import { useEffect, useState } from "react";
import { LayoutGrid, List } from "lucide-react";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "rambla.view_intro_seen";

/**
 * Modal de bienvenida que aparece una sola vez (localStorage flag) para que
 * el visitante elija entre Grid y Lista, y aprenda dónde está el toggle
 * para cambiarlo después.
 *
 * Se cierra:
 *  - Eligiendo una opción → marca como visto + setView.
 *  - Click afuera / ESC → marca como visto sin elegir (default vigente).
 */
export function ViewIntroDialog({ onPick }: { onPick: (mode: "grid" | "list") => void }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (localStorage.getItem(STORAGE_KEY) === "1") return;
    // Pequeño delay para que la primera pintura cargue antes y se sienta
    // menos invasivo (la página ya existe atrás).
    const t = setTimeout(() => setOpen(true), 350);
    return () => clearTimeout(t);
  }, []);

  const markSeen = () => {
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch { /* ignore */ }
  };

  const handlePick = (mode: "grid" | "list") => {
    markSeen();
    setOpen(false);
    onPick(mode);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) markSeen();
        setOpen(v);
      }}
    >
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">
            ¿Cómo querés ver el catálogo?
          </DialogTitle>
          <DialogDescription>
            Elegí una vista. Podés cambiarla cuando quieras desde el botón arriba a la derecha.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-3 py-2">
          <ViewOption
            icon={<LayoutGrid className="h-7 w-7" strokeWidth={1.5} />}
            label="Grilla"
            description="Cards con foto. Ideal para explorar visualmente."
            onClick={() => handlePick("grid")}
          />
          <ViewOption
            icon={<List className="h-7 w-7" strokeWidth={1.5} />}
            label="Lista"
            description="Filas compactas con specs. Más rápido para buscar."
            onClick={() => handlePick("list")}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ViewOption({
  icon, label, description, onClick,
}: {
  icon: React.ReactNode;
  label: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "group flex flex-col items-start gap-2 rounded-lg border hairline p-4 text-left transition",
        "hover:border-amber hover:bg-amber-soft/40 active:bg-amber-soft/60",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber",
      )}
    >
      <span className="text-ink">{icon}</span>
      <span className="font-display text-base text-ink">{label}</span>
      <span className="text-xs text-muted-foreground leading-snug">{description}</span>
    </button>
  );
}
