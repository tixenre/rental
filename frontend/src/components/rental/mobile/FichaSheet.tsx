import { Button } from "@/design-system/ui/button";
import { type Equipment } from "@/data/equipment";
import { ShareButton } from "@/components/rental/equipment/shared/ShareButton";
import { EquipoFoto } from "@/components/rental/EquipoFoto";
import { formatARS } from "@/lib/format";
import { CatIcon, SheetClose } from "./shared";

/* ── FichaSheet ──────────────────────────────────────────────────── */
interface FichaSheetProps {
  eq: Equipment;
  onClose: () => void;
  onAddToCart: (id: string, delta: number) => void;
  inCart: number;
  jornadas: number;
  fechaDesde: Date | null;
}

export function FichaSheet({
  eq,
  onClose,
  onAddToCart,
  inCart,
  jornadas,
  fechaDesde,
}: FichaSheetProps) {
  const specsText = eq.specs.map((s) => `${s.label}: ${s.value}`).join(" · ");

  return (
    <>
      <div
        className="fixed inset-0 z-[60] bg-scrim animate-in fade-in duration-200"
        onClick={onClose}
      />
      <div
        className="fixed inset-x-0 bottom-0 z-[61] bg-card flex flex-col animate-in slide-in-from-bottom duration-[260ms]"
        style={{
          height: "72%",
          maxHeight: "72%",
          borderRadius: "24px 24px 0 0",
          boxShadow: "0 -8px 40px rgba(0,0,0,0.18)",
        }}
      >
        <div className="w-9 h-1 rounded-full bg-hairline mx-auto mt-2.5 shrink-0" />
        <div className="flex items-start justify-between px-5 py-3 border-b border-hairline shrink-0">
          <div>
            <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground">
              {eq.brand} · {eq.category}
            </div>
            <div className="font-sans text-base font-bold text-ink mt-0.5">{eq.name}</div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <ShareButton item={eq} size="md" />
            <SheetClose onClose={onClose} />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: "none" }}>
          {/* Photo */}
          <div
            className="mx-5 mt-3.5 rounded-[var(--radius-lg)] border border-hairline bg-surface flex items-center justify-center text-muted-foreground overflow-hidden"
            style={{ aspectRatio: "4/3" }}
          >
            <EquipoFoto
              foto={eq}
              alt={eq.name}
              sizes="(max-width: 640px) 92vw, 400px"
              loading="lazy"
              className="w-full h-full object-contain p-4"
              fallback={<CatIcon cat={eq.category} size={48} />}
            />
          </div>

          {/* Price */}
          <div className="px-5 pt-3.5 flex justify-between items-baseline">
            <div>
              <div
                className="font-mono font-bold leading-none"
                style={{ fontSize: 22, fontVariantNumeric: "tabular-nums" }}
              >
                {fechaDesde ? formatARS(eq.pricePerDay * jornadas) : formatARS(eq.pricePerDay)}
              </div>
              <div className="font-mono text-2xs tracking-[0.18em] uppercase text-muted-foreground mt-0.5">
                {fechaDesde
                  ? `${jornadas} ${jornadas === 1 ? "jornada" : "jornadas"}`
                  : "/ jornada"}
              </div>
            </div>
            {eq.cantidad != null && (
              <div className="font-mono text-xs text-muted-foreground">
                {eq.cantidad} {eq.cantidad === 1 ? "disponible" : "disponibles"}
              </div>
            )}
          </div>

          {/* Specs */}
          <div className="px-5 py-3 border-b border-hairline">
            <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground mb-1">
              Especificaciones
            </div>
            <div className="font-sans text-sm text-muted-foreground leading-relaxed">
              {eq.description || specsText || "—"}
            </div>
            {eq.specs.length > 0 && (
              <div className="mt-2 flex flex-col gap-0.5">
                {eq.specs.map((s, i) => (
                  <div key={i} className="font-sans text-xs text-muted-foreground">
                    <span className="font-semibold text-ink/70">{s.label}:</span> {s.value}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Includes */}
          {eq.includes && eq.includes.length > 0 && (
            <div className="px-5 py-3 border-b border-hairline">
              <div className="font-mono text-2xs tracking-[0.2em] uppercase text-muted-foreground mb-1.5">
                Incluye
              </div>
              <div className="flex flex-wrap gap-1.5">
                {eq.includes.map((item, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 rounded-full border border-hairline bg-surface font-sans text-xs text-ink"
                  >
                    ✓ {item.name}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="h-4" />
        </div>

        {/* Footer */}
        <div className="px-5 pt-3 border-t border-hairline shrink-0" style={{ paddingBottom: 20 }}>
          {inCart > 0 ? (
            <div
              className="flex items-center justify-between px-3.5 py-2.5 rounded-full"
              style={{ background: "var(--amber)", border: "1.5px solid var(--amber)" }}
            >
              <button
                className="w-9 h-9 grid place-items-center text-ink font-bold text-xl"
                onClick={() => onAddToCart(eq.id, -1)}
              >
                −
              </button>
              <span className="font-mono text-sm font-bold text-ink">{inCart} en carrito</span>
              <button
                className="w-9 h-9 grid place-items-center text-ink font-bold text-xl disabled:opacity-40"
                onClick={() => onAddToCart(eq.id, 1)}
                disabled={eq.cantidad != null && inCart >= eq.cantidad}
              >
                +
              </button>
            </div>
          ) : (
            <Button
              variant="primary"
              shape="pill"
              className="w-full h-auto py-3.5 font-sans text-15 font-bold"
              onClick={() => {
                onAddToCart(eq.id, 1);
                onClose();
              }}
            >
              Agregar al carrito
            </Button>
          )}
        </div>
      </div>
    </>
  );
}
