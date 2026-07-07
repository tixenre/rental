import { useState } from "react";
import { Check } from "lucide-react";
import { BottomSheet } from "@/components/mobile/BottomSheet";
import { cn } from "@/lib/utils";

/* ── BrandSheet ──────────────────────────────────────────────────── */
type BrandSheetItem = {
  nombre: string;
  logo_url: string | null;
  destacada: boolean;
  count: number;
};

export function BrandSheet({
  open,
  onOpenChange,
  brands,
  selected,
  onSelect,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  brands: BrandSheetItem[];
  selected: string | null;
  onSelect: (brand: string | null) => void;
}) {
  return (
    <BottomSheet open={open} onOpenChange={onOpenChange} title="Marca" showClose>
      <div className="px-4 py-3 space-y-1">
        <button
          type="button"
          onClick={() => {
            onSelect(null);
            onOpenChange(false);
          }}
          className={cn(
            "w-full flex items-center justify-between gap-2 rounded-lg px-3 py-3 text-left transition",
            selected === null
              ? "bg-amber-soft border border-amber/40"
              : "border border-hairline hover:bg-muted",
          )}
        >
          <span className="font-sans text-sm font-semibold text-ink">Todas las marcas</span>
          {selected === null && <Check className="h-4 w-4 text-amber" />}
        </button>
        {brands.map((b) => {
          const active = selected === b.nombre;
          return (
            <button
              key={b.nombre}
              type="button"
              onClick={() => {
                onSelect(active ? null : b.nombre);
                onOpenChange(false);
              }}
              className={cn(
                "w-full flex items-center justify-between gap-2 rounded-lg px-3 py-2.5 text-left transition",
                active
                  ? "bg-amber-soft border border-amber/40"
                  : "border border-hairline hover:bg-muted",
              )}
            >
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <BrandLogo nombre={b.nombre} logo_url={b.logo_url} />
                <div className="min-w-0 flex-1">
                  <div className="font-sans text-sm font-semibold text-ink truncate">
                    {b.nombre}
                  </div>
                  {b.destacada && (
                    <div className="font-mono text-xs uppercase tracking-[0.18em] text-amber/80 mt-0.5">
                      Destacada
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="font-mono text-2xs tabular-nums text-muted-foreground">
                  {b.count}
                </span>
                {active && <Check className="h-4 w-4 text-amber" />}
              </div>
            </button>
          );
        })}
        {brands.length === 0 && (
          <div className="text-center py-8 text-sm text-muted-foreground">
            No hay marcas con equipos en la categoría actual.
          </div>
        )}
      </div>
    </BottomSheet>
  );
}

function BrandLogo({ nombre, logo_url }: { nombre: string; logo_url: string | null }) {
  const [failed, setFailed] = useState(false);
  if (logo_url && !failed) {
    return (
      <div className="h-9 w-9 rounded-md bg-white border border-hairline grid place-items-center shrink-0 overflow-hidden p-1">
        <img
          src={logo_url}
          alt={nombre}
          className="max-h-full max-w-full object-contain"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      </div>
    );
  }
  // Fallback: cuadradito con las iniciales (estilo de BrandCard del desktop).
  const inicial = (nombre[0] ?? "?").toUpperCase();
  return (
    <div className="h-9 w-9 rounded-md bg-muted border border-hairline grid place-items-center shrink-0 font-display text-base font-black text-ink">
      {inicial}
    </div>
  );
}
