import { useState } from "react";
import { Plus, Minus, Sparkles, Share2, Check } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { useCart } from "@/lib/cart-store";
import { type Equipment } from "@/data/equipment";
import { formatARS } from "@/lib/format";
import { EmptyImage } from "./EmptyImage";
import { IncludedList } from "./IncludedList";

export function EquipmentDetailDialog({
  item,
  open,
  onOpenChange,
  disponible,
}: {
  item: Equipment;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  disponible?: number;
}) {
  const qty = useCart((s) => s.items[item.id] ?? 0);
  const add = useCart((s) => s.add);
  const [copied, setCopied] = useState(false);

  const sinStock = disponible !== undefined && disponible <= 0;
  const canAddMore = disponible === undefined || qty < disponible;

  const handleShare = async () => {
    if (typeof window === "undefined") return;
    const url = `${window.location.origin}${window.location.pathname}?eq=${item.id}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: item.name, url });
      } else {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      }
    } catch {
      /* cancelled */
    }
  };
  const remove = useCart((s) => s.remove);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            <span>{item.brand}</span>
            <span>·</span>
            <span>{item.category}</span>
            {item.isNew && (
              <span className="inline-flex items-center gap-0.5 rounded-full bg-ink px-1.5 py-0.5 text-amber">
                <Sparkles className="h-2.5 w-2.5" /> nuevo
              </span>
            )}
            {item.isCombo && (
              <span className="rounded-full bg-amber px-1.5 py-0.5 text-ink">combo</span>
            )}
          </div>
          <div className="flex items-start justify-between gap-3">
            <DialogTitle className="font-display text-2xl leading-tight">{item.name}</DialogTitle>
            <button
              type="button"
              onClick={handleShare}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-full border hairline px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground transition hover:border-amber hover:text-ink"
              aria-label="Compartir enlace"
            >
              {copied ? (
                <>
                  <Check className="h-3 w-3" /> Copiado
                </>
              ) : (
                <>
                  <Share2 className="h-3 w-3" /> Compartir
                </>
              )}
            </button>
          </div>
          <DialogDescription className="sr-only">
            Detalle del equipo {item.name}
          </DialogDescription>
        </DialogHeader>

        <div className="relative aspect-[16/9] overflow-hidden rounded-lg">
          {item.fotoUrl ? (
            <img
              src={item.fotoUrl}
              alt={item.name}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <EmptyImage category={item.category} brand={item.brand} />
          )}
        </div>

        {item.description && (
          <div className="space-y-2">
            <h3 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Descripción
            </h3>
            <p className="text-sm leading-relaxed text-foreground/90 whitespace-pre-line">
              {item.description}
            </p>
          </div>
        )}

        {item.specs && item.specs.length > 0 && (
          <div className="space-y-2">
            <h3 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Especificaciones
            </h3>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
              {item.specs.map((s, i) => (
                <div key={i} className="flex justify-between gap-3 border-b hairline py-1.5 text-sm">
                  <dt className="text-muted-foreground">{s.label}</dt>
                  <dd className="text-right font-medium text-ink tabular">{s.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        <IncludedList item={item} />

        <div className="flex items-end justify-between gap-3 border-t hairline pt-4">
          <div>
            <div className="font-display text-2xl tabular text-ink">
              {formatARS(item.pricePerDay)}
            </div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              / 1 jornada
            </div>
          </div>

          {qty === 0 ? (
            <button
              onClick={() => !sinStock && add(item.id)}
              disabled={sinStock}
              className="inline-flex items-center gap-1.5 rounded-md bg-ink px-4 py-2.5 text-sm font-medium uppercase tracking-wider text-amber transition hover:bg-foreground disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Plus className="h-4 w-4" /> Agregar al carrito
            </button>
          ) : (
            <div className="flex items-center gap-1 rounded-md border border-amber/40 bg-amber-soft p-1">
              <button
                onClick={() => remove(item.id)}
                className="grid h-9 w-9 place-items-center rounded text-amber hover:bg-amber/20"
              >
                <Minus className="h-4 w-4" />
              </button>
              <span className="w-8 text-center text-base font-semibold tabular">{qty}</span>
              <button
                onClick={() => canAddMore && add(item.id)}
                disabled={!canAddMore}
                className="grid h-9 w-9 place-items-center rounded text-amber hover:bg-amber/20 disabled:opacity-40"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
