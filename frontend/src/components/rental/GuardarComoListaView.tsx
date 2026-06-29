import { useState } from "react";
import { Check, X as XIcon, ListPlus } from "lucide-react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";

/**
 * GuardarComoListaView — el SHELL del gesto "Guardar como lista" (botón ↔ input inline).
 *
 * Presentacional: maneja el toggle botón↔input, el nombre y el estado busy, pero NO
 * sabe del backend. Recibe `onSave(nombre)` (que devuelve si se guardó) — el container
 * `GuardarComoListaButton` lo implementa con `clienteApi.crearLista`; la vitrina del DS
 * le pasa un mock. Enter guarda, Escape cancela; tras guardar vuelve al botón.
 */
export function GuardarComoListaView({
  onSave,
  disabled = false,
  className,
  placeholder = "Nombre de la lista",
}: {
  /** Guarda la lista con ese nombre; devuelve true si se guardó (para resetear). */
  onSave: (nombre: string) => Promise<boolean>;
  disabled?: boolean;
  className?: string;
  placeholder?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [nombre, setNombre] = useState("");
  const [busy, setBusy] = useState(false);

  async function guardar() {
    const limpio = nombre.trim();
    if (!limpio) {
      toast.error("La lista necesita un nombre.");
      return;
    }
    setBusy(true);
    try {
      const ok = await onSave(limpio);
      if (ok) {
        setEditing(false);
        setNombre("");
      }
    } finally {
      setBusy(false);
    }
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        disabled={disabled}
        className={cn(
          "inline-flex w-full items-center justify-center gap-1.5 text-xs text-muted-foreground transition hover:text-ink focus:outline-none focus-visible:underline disabled:opacity-40",
          className,
        )}
      >
        <ListPlus className="h-3.5 w-3.5" />
        Guardar como lista
      </button>
    );
  }

  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      <input
        autoFocus
        type="text"
        value={nombre}
        onChange={(e) => setNombre(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") guardar();
          if (e.key === "Escape") {
            setNombre("");
            setEditing(false);
          }
        }}
        maxLength={80}
        placeholder={placeholder}
        aria-label="Nombre de la lista"
        className="min-w-0 flex-1 rounded-lg border hairline bg-card px-3 py-2 font-sans text-sm text-ink outline-none transition focus:border-ink"
      />
      <button
        type="button"
        onClick={guardar}
        disabled={busy}
        className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-ink text-amber transition hover:bg-amber hover:text-ink disabled:opacity-40"
        aria-label="Guardar lista"
      >
        <Check className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => {
          setNombre("");
          setEditing(false);
        }}
        className="grid h-11 w-11 shrink-0 place-items-center rounded-lg border hairline text-muted-foreground transition hover:border-ink hover:text-ink"
        aria-label="Cancelar"
      >
        <XIcon className="h-4 w-4" />
      </button>
    </div>
  );
}
