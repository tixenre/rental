import { type Brand } from "@/types/brand";
import { cn } from "@/lib/utils";

export function BrandCard({
  brand,
  count,
  isSelected,
  onClick,
}: {
  brand: Brand;
  count: number;
  isSelected?: boolean;
  onClick: () => void;
}) {
  const logoUrl = brand.logo_url;
  const placeholder = "https://via.placeholder.com/120?text=" + encodeURIComponent(brand.nombre);

  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative flex h-32 w-32 flex-shrink-0 flex-col items-center justify-center gap-2 rounded-lg border transition",
        isSelected
          ? "border-amber bg-amber-soft"
          : "border-hairline bg-surface hover:border-ink hover:bg-amber-soft"
      )}
    >
      {/* Logo/Photo */}
      <div className="h-16 w-16 overflow-hidden rounded">
        <img
          src={logoUrl || placeholder}
          alt={brand.nombre}
          className="h-full w-full object-cover"
          onError={(e) => {
            (e.target as HTMLImageElement).src = placeholder;
          }}
        />
      </div>

      {/* Nombre + contador */}
      <div className="flex flex-col items-center gap-1 text-center">
        <span className="text-sm font-display leading-tight text-ink line-clamp-2">
          {brand.nombre}
        </span>
        <span className="font-mono text-[10px] tabular text-muted-foreground">
          {count}
        </span>
      </div>
    </button>
  );
}
