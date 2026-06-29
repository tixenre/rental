/**
 * CompartirComposicionButton.tsx — Control "Compartir" (#1092 feature #4).
 *
 * Entrada ÚNICA para compartir una composición de equipos por un link público
 * (`/c/<token>`): el caso gaffer → productor ("che, reservá esto").
 *
 * Un solo click, sin pedir título: crea el link y dispara el share nativo del SO
 * (mobile) o lo copia al portapapeles (desktop) vía `shareLink`. El título es
 * opcional y la preview ya describe el listado, así que no lo pedimos — el gesto
 * es directo, como cualquier botón de "compartir" estándar.
 *
 * Es PÚBLICO: anda logueado o anónimo (la puerta `/api/public/compartir` no pide
 * sesión). Guarda SOLO la composición (`equipo_id` + `cantidad`); el destinatario
 * la resuelve en vivo contra el catálogo y la rearma con `rearmarCarrito`.
 */
import { useState } from "react";
import { Share2 } from "lucide-react";
import { toast } from "sonner";
import { crearCompartido, type CompartirItem } from "@/lib/compartir";
import { shareLink } from "@/lib/share";
import { cn } from "@/lib/utils";

export function CompartirComposicionButton({
  items,
  className,
}: {
  /** Composición a compartir (equipo_id + cantidad). El backend dedup/clampa/filtra. */
  items: CompartirItem[];
  className?: string;
}) {
  const [busy, setBusy] = useState(false);

  const vacio = items.length === 0;

  async function compartir() {
    if (vacio) {
      toast.info("Agregá equipos antes de compartir.");
      return;
    }
    setBusy(true);
    try {
      const { url } = await crearCompartido(items, null);
      const res = await shareLink(url);
      if (res === "copied") toast.success("Copiamos el link para compartir.");
      else if (res === "shared") toast.success("¡Link listo para compartir!");
      // "cancelled" (cerró la hoja de compartir nativa) → sin toast, no es error.
    } catch (e) {
      toast.error((e as Error).message || "No se pudo crear el link.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={compartir}
      disabled={vacio || busy}
      className={cn(
        "inline-flex w-full items-center justify-center gap-1.5 text-xs text-muted-foreground transition hover:text-ink focus:outline-none focus-visible:underline disabled:opacity-40",
        className,
      )}
    >
      <Share2 className="h-3.5 w-3.5" />
      Compartir
    </button>
  );
}
