import { useState } from "react";
import { Check, Share2 } from "lucide-react";

export function ShareEquipmentButton({ id, name }: { id: string; name: string }) {
  const [copied, setCopied] = useState(false);

  const handleShare = async () => {
    if (typeof window === "undefined") return;
    const url = `${window.location.origin}${window.location.pathname}?eq=${id}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: name, url });
      } else {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      }
    } catch {
      /* cancelled */
    }
  };

  return (
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
  );
}
