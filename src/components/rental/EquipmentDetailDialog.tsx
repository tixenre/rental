import { useState } from "react";
import { Plus, Minus, Sparkles, Share2, Check, ChevronDown } from "lucide-react";
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
import { KeywordChips } from "./KeywordChips";

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
  const [specsOpen, setSpecsOpen] = useState(false);
  const [descExpanded, setDescExpanded] = useState(false);
  const DESC_LIMIT = 240;
  const desc = item.description ?? "";
  const isLongDesc = desc.length > DESC_LIMIT;
  const shownDesc = !isLongDesc || descExpanded ? desc : desc.slice(0, DESC_LIMIT).trimEnd() + "…";

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

        {item.keywords && item.keywords.length > 0 && (
          <KeywordChips keywords={item.keywords} />
        )}

        {desc && (
          <div className="space-y-2">
            <h3 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Descripción
            </h3>
            <p className="text-sm leading-relaxed text-foreground/90 whitespace-pre-line">
              {shownDesc}
            </p>
            {isLongDesc && (
              <button
                type="button"
                onClick={() => setDescExpanded((v) => !v)}
                className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground underline-offset-4 transition hover:text-ink hover:underline"
                aria-expanded={descExpanded}
              >
                {descExpanded ? "Ver menos" : "Ver más"}
              </button>
            )}
          </div>
        )}

        <QuickFactsRow item={item} />

        {item.specs && item.specs.length > 0 && (
          <div className="border-t border-b hairline">
            <button
              type="button"
              onClick={() => setSpecsOpen((v) => !v)}
              aria-expanded={specsOpen}
              aria-controls="specs-panel"
              className="flex w-full items-center justify-between gap-3 py-3 text-left transition hover:text-ink"
            >
              <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
                Especificaciones
                <span className="ml-2 text-ink/60">({item.specs.length})</span>
              </span>
              <ChevronDown
                className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${specsOpen ? "rotate-180" : ""}`}
              />
            </button>
            <div
              id="specs-panel"
              hidden={!specsOpen}
              className="pb-3"
            >
              <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
                {item.specs.map((s, i) => (
                  <div key={i} className="flex justify-between gap-3 border-b hairline py-1.5 text-sm">
                    <dt className="text-muted-foreground">{s.label}</dt>
                    <dd className="text-right font-medium text-ink tabular">{s.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        )}

        {item.incluye && item.incluye.length > 0 && (
          <FichaPillSection title="Incluye en la caja" items={item.incluye} />
        )}
        {item.conectividad && item.conectividad.length > 0 && (
          <FichaPillSection title="Conectividad" items={item.conectividad} />
        )}
        {item.compatibleCon && item.compatibleCon.length > 0 && (
          <FichaPillSection title="Compatible con" items={item.compatibleCon} />
        )}

        {item.videoUrl && <YouTubeEmbed url={item.videoUrl} />}

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

/** Pills compactas con los datos físicos / técnicos clave (peso, dimensiones, montura, etc). */
function QuickFactsRow({ item }: { item: Equipment }) {
  const facts: { label: string; value: string }[] = [];
  if (item.montura) facts.push({ label: "Montura", value: item.montura });
  if (item.formato) facts.push({ label: "Formato", value: item.formato });
  if (item.resolucion) facts.push({ label: "Resolución", value: item.resolucion });
  if (item.peso) facts.push({ label: "Peso", value: item.peso });
  if (item.dimensiones) facts.push({ label: "Dimensiones", value: item.dimensiones });
  if (item.alimentacion) facts.push({ label: "Alimentación", value: item.alimentacion });
  if (facts.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {facts.map((f) => (
        <span
          key={f.label}
          className="inline-flex items-center gap-1.5 rounded-full border hairline bg-muted/30 px-2.5 py-1 text-[11px]"
        >
          <span className="font-mono uppercase tracking-wider text-muted-foreground">
            {f.label}
          </span>
          <span className="font-medium text-ink">{f.value}</span>
        </span>
      ))}
    </div>
  );
}

function FichaPillSection({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="space-y-2">
      <h3 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
        {title}
      </h3>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item, i) => (
          <span
            key={`${title}-${i}`}
            className="inline-flex items-center rounded-md border hairline bg-background px-2 py-1 text-[12px] text-ink/90"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function YouTubeEmbed({ url }: { url: string }) {
  const id = (() => {
    try {
      const u = new URL(url);
      if (u.hostname === "youtu.be") return u.pathname.slice(1);
      if (u.hostname.includes("youtube.com")) {
        const v = u.searchParams.get("v");
        if (v) return v;
        const m = u.pathname.match(/\/(?:embed|shorts)\/([\w-]+)/);
        if (m) return m[1];
      }
    } catch { /* invalid url */ }
    return null;
  })();
  if (!id) return null;
  return (
    <div className="space-y-2">
      <h3 className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
        Video demo
      </h3>
      <div className="relative w-full overflow-hidden rounded-md border hairline" style={{ aspectRatio: "16 / 9" }}>
        <iframe
          src={`https://www.youtube.com/embed/${id}`}
          title="Video demo"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
          loading="lazy"
          className="absolute inset-0 h-full w-full"
        />
      </div>
    </div>
  );
}
