import { useEffect, useState } from "react";
import { LayoutGrid, List } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "rambla.view_intro_seen";

/**
 * Modal de bienvenida que aparece una sola vez (localStorage flag) en
 * desktop para que el visitante elija entre Grid y Lista, y aprenda
 * dónde está el toggle para cambiarlo después.
 *
 * Solo desktop: en mobile el default es Lista (más eficiente para
 * pantalla chica) y no hay sub-decisión que hacer.
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
    // Solo desktop. Triple chequeo para cubrir:
    //  - phones/tablets con cualquier ancho (incluso landscape).
    //  - dispositivos principalmente táctiles.
    //  - user agents identificables como mobile.
    const mql = window.matchMedia;
    if (!mql) return;
    const isNarrow = mql("(max-width: 767px)").matches;
    const isCoarse = mql("(pointer: coarse)").matches;
    const ua = (navigator.userAgent || "").toLowerCase();
    const looksMobile = /android|iphone|ipad|ipod|mobile|tablet/.test(ua);
    if (isNarrow || isCoarse || looksMobile) return;
    // Pequeño delay para que la primera pintura cargue antes y se sienta
    // menos invasivo (la página ya existe atrás).
    const t = setTimeout(() => setOpen(true), 400);
    return () => clearTimeout(t);
  }, []);

  const markSeen = () => {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
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
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">¿Cómo querés ver el catálogo?</DialogTitle>
          <DialogDescription>
            Hay dos formas. Elegí la que te resulte más cómoda — podés cambiar cuando quieras desde
            el botón con los íconos de grilla y lista, arriba a la derecha.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 gap-2 py-2 sm:grid-cols-2 sm:gap-3">
          <ViewOption
            icon={<LayoutGrid className="h-8 w-8" strokeWidth={1.5} />}
            label="Grilla"
            tagline="Para explorar visualmente"
            bullets={[
              "Foto grande de cada equipo",
              "Comparás opciones de un vistazo",
              "Ideal si no sabés exactamente qué buscás",
            ]}
            onClick={() => handlePick("grid")}
          />
          <ViewOption
            icon={<List className="h-8 w-8" strokeWidth={1.5} />}
            label="Lista"
            tagline="Para comparar specs rápido"
            bullets={[
              "Más equipos visibles por pantalla",
              "Ves marca, modelo y specs sin abrir",
              "Ideal si ya sabés más o menos qué buscás",
            ]}
            onClick={() => handlePick("list")}
          />
        </div>

        <p className="text-[11px] text-muted-foreground text-center pt-1">
          Tu elección se guarda en este navegador. Podés volver a cambiarla en cualquier momento.
        </p>
      </DialogContent>
    </Dialog>
  );
}

function ViewOption({
  icon,
  label,
  tagline,
  bullets,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  tagline: string;
  bullets: string[];
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "group flex flex-col gap-2 rounded-lg border hairline p-4 text-left transition",
        "hover:border-amber hover:bg-amber-soft/40 active:bg-amber-soft/60",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber",
      )}
    >
      <div className="flex items-center gap-2.5">
        <span className="text-ink">{icon}</span>
        <span className="font-display text-lg text-ink">{label}</span>
      </div>
      <span className="text-xs font-medium text-ink/80">{tagline}</span>
      <ul className="space-y-1 text-[11px] text-muted-foreground leading-snug">
        {bullets.map((b) => (
          <li key={b} className="flex gap-1.5">
            <span className="text-amber shrink-0" aria-hidden>
              ·
            </span>
            <span>{b}</span>
          </li>
        ))}
      </ul>
    </button>
  );
}
