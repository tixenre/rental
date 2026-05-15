import type { Category } from "@/data/equipment";
import { CategoryIllustration } from "./illustrations/CategoryIllustration";

export function EmptyImage({
  category,
  brand,
  className = "",
}: {
  category: string;
  brand: string;
  className?: string;
}) {
  return (
    <div
      className={`relative flex h-full w-full items-center justify-center overflow-hidden bg-amber-soft ${className}`}
    >
      <div className="absolute inset-0 grain opacity-30" />
      <CategoryIllustration
        category={category}
        className="relative z-10 h-24 w-24 text-amber"
      />
      <div className="absolute bottom-2 left-3 font-mono text-[10px] uppercase tracking-widest text-foreground/35">
        {brand}
      </div>
      <div className="absolute top-2 right-3 font-mono text-[9px] uppercase tracking-widest text-foreground/25">
        {category}
      </div>
    </div>
  );
}
