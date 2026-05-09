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
}: {
  item: Equipment;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const qty = useCart((s) => s.items[item.id] ?? 0);
  const add = useCart((s) => s.add);
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
          <DialogTitle className="font-display text-2xl leading-tight">{item.name}</DialogTitle>
          <DialogDescription className="sr-only">
            Detalle del equipo {item.name}
          </DialogDescription>
        </DialogHeader>

        <div className="relative aspect-[16/9] overflow-hidden rounded-lg">
          <EmptyImage category={item.category} brand={item.brand} />
        </div>

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
              onClick={() => add(item.id)}
              className="inline-flex items-center gap-1.5 rounded-md bg-ink px-4 py-2.5 text-sm font-medium uppercase tracking-wider text-amber transition hover:bg-foreground"
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
                onClick={() => add(item.id)}
                className="grid h-9 w-9 place-items-center rounded text-amber hover:bg-amber/20"
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
