import {
  Battery,
  Camera,
  Layers,
  Mic,
  Monitor,
  Package,
  SlidersHorizontal,
  Sun,
  X,
  Zap,
} from "lucide-react";

/* ── Category icon ───────────────────────────────────────────────── */
type IconComp = React.ComponentType<{ size?: number; className?: string; strokeWidth?: number }>;

const CAT_ICONS: Record<string, IconComp> = {
  Cámaras: Camera,
  Lentes: Sun, // Aperture not in lucide-react standard; Sun as fallback
  Luces: Sun,
  Iluminación: Sun,
  Tungsteno: Sun,
  Sonido: Mic,
  Audio: Mic,
  Trípode: Layers,
  Soportes: Layers,
  Stands: Layers,
  Monitores: Monitor,
  Flash: Zap,
  Baterías: Battery,
  Filtros: SlidersHorizontal,
  Comunicación: Monitor,
  Modificadores: Sun,
  "Brazo Mágico": Layers,
  Grips: Layers,
};

export function CatIcon({ cat, size = 20 }: { cat: string; size?: number }) {
  const Icon = CAT_ICONS[cat] ?? Package;
  return <Icon size={size} strokeWidth={1.5} />;
}

/* ── SheetClose button ───────────────────────────────────────────── */
export function SheetClose({ onClose }: { onClose: () => void }) {
  return (
    <button
      onClick={onClose}
      className="relative w-[30px] h-[30px] rounded-full bg-muted grid place-items-center text-muted-foreground hover:bg-ink/10 hover:text-ink transition-colors before:absolute before:left-1/2 before:top-1/2 before:h-11 before:w-11 before:-translate-x-1/2 before:-translate-y-1/2 before:content-['']"
    >
      <X size={14} strokeWidth={2.5} />
    </button>
  );
}
