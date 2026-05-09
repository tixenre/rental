import { Camera, Aperture, Lightbulb, Mic, Tripod, Package, Cable } from "lucide-react";
import type { Category } from "@/data/equipment";

const map: Record<Category, React.ComponentType<{ className?: string }>> = {
  Cámaras: Camera,
  Lentes: Aperture,
  Iluminación: Lightbulb,
  Audio: Mic,
  Soportes: Tripod,
  Accesorios: Package,
  Adaptadores: Cable,
};

export function EmptyImage({
  category,
  brand,
  className = "",
}: {
  category: Category;
  brand: string;
  className?: string;
}) {
  const Icon = map[category] ?? Package;
  return (
    <div
      className={`relative flex h-full w-full items-center justify-center overflow-hidden bg-surface-elevated ${className}`}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-amber/[0.04] via-transparent to-amber/[0.08]" />
      <div className="absolute inset-0 grain opacity-40" />
      <Icon className="relative z-10 h-12 w-12 text-foreground/15" strokeWidth={1} />
      <div className="absolute bottom-2 left-3 font-mono text-[10px] uppercase tracking-widest text-foreground/25">
        {brand}
      </div>
    </div>
  );
}
