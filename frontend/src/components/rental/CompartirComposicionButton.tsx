/**
 * CompartirComposicionButton.tsx — Control "Compartir" (#1092 feature #4).
 *
 * Entrada ÚNICA para compartir una composición de equipos por un link público
 * (`/c/<token>`): el caso gaffer → productor ("che, reservá esto"). Gemelo de
 * `GuardarComoListaButton` (mismo gesto inline botón↔input), con dos diferencias:
 *
 *  1. El título es OPCIONAL (skippable) — Enter o el check comparten igual, con o
 *     sin título. La lista exige nombre; el link no.
 *  2. Es PÚBLICO: anda logueado o anónimo (la puerta `/api/public/compartir` no
 *     pide sesión). Crea el link y dispara el share nativo / copia vía `shareLink`.
 *
 * Guarda SOLO la composición (`equipo_id` + `cantidad`); el destinatario la
 * resuelve en vivo contra el catálogo y la rearma con `rearmarCarrito`.
 */
import { useState } from "react";
import { Check, X as XIcon, Share2 } from "lucide-react";
import { toast } from "sonner";
import { crearCompartido, type CompartirItem } from "@/lib/compartir";
import { shareLink } from "@/lib/share";
import { cn } from "@/lib/utils";

export function CompartirComposicionButton({
  items,
  className,
  placeholder = "Título (opcional)",
}: {
  /** Composición a compartir (equipo_id + cantidad). El backend dedup/clampa/filtra. */
  items: CompartirItem[];
  className?: string;
  placeholder?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [titulo, setTitulo] = useState("");
  const [busy, setBusy] = useState(false);

  const vacio = items.length === 0;

  function reset() {
    setTitulo("");
    setEditing(false);
  }

  async function compartir() {
    if (vacio) {
      toast.info("Agregá equipos antes de compartir.");
      return;
    }
    const limpio = titulo.trim();
    setBusy(true);
    try {
      const { url } = await crearCompartido(items, limpio || null);
      const res = await shareLink(url, limpio || undefined);
      if (res === "copied") toast.success("Copiamos el link para compartir.");
      else if (res === "shared") toast.success("¡Link listo para compartir!");
      reset();
    } catch (e) {
      toast.error((e as Error).message || "No se pudo crear el link.");
    } finally {
      setBusy(false);
    }
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        disabled={vacio}
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

  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      <input
        autoFocus
        type="text"
        value={titulo}
        onChange={(e) => setTitulo(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") compartir();
          if (e.key === "Escape") reset();
        }}
        maxLength={80}
        placeholder={placeholder}
        aria-label="Título del link (opcional)"
        className="min-w-0 flex-1 rounded-lg border hairline bg-card px-3 py-2 font-sans text-sm text-ink outline-none transition focus:border-ink"
      />
      <button
        type="button"
        onClick={compartir}
        disabled={busy}
        className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-ink text-amber transition hover:bg-amber hover:text-ink disabled:opacity-40"
        aria-label="Compartir"
      >
        <Check className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={reset}
        className="grid h-11 w-11 shrink-0 place-items-center rounded-lg border hairline text-muted-foreground transition hover:border-ink hover:text-ink"
        aria-label="Cancelar"
      >
        <XIcon className="h-4 w-4" />
      </button>
    </div>
  );
}
