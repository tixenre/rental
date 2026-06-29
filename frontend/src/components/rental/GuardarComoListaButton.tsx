/**
 * GuardarComoListaButton.tsx — Control "Guardar como lista" (#1092).
 *
 * Entrada ÚNICA para crear una lista / kit personal a partir de una composición
 * de equipos (el carrito actual o un pedido viejo). Una lista guarda SOLO la
 * composición (`equipo_id` + `cantidad`); nombre/foto/precio se resuelven en
 * vivo desde el catálogo (igual que favoritos).
 *
 * - Logueado-only: las listas son server-only (acción deliberada). El caller
 *   decide si renderizarlo (el carrito lo gatea a `clienteSession`; la card de
 *   pedido vive dentro del portal, siempre logueado).
 * - Llama `clienteApi.crearLista` ONE-SHOT — NO usa el hook `useListas` (no hay
 *   que traer todas las listas en una superficie que solo crea una).
 * - Nombre por input inline (NO `window.prompt`, regla del DS). Enter guarda,
 *   Escape cancela. Tras guardar, vuelve al botón (el toast confirma).
 */
import { useState } from "react";
import { Check, X as XIcon, ListPlus } from "lucide-react";
import { toast } from "sonner";
import { clienteApi, type ListaItem } from "@/lib/cliente/api";
import { cn } from "@/lib/utils";

export function GuardarComoListaButton({
  items,
  className,
  placeholder = "Nombre de la lista",
}: {
  /** Composición a guardar (equipo_id + cantidad). El backend dedup/clampa/filtra. */
  items: ListaItem[];
  className?: string;
  placeholder?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [nombre, setNombre] = useState("");
  const [busy, setBusy] = useState(false);

  const vacio = items.length === 0;

  async function guardar() {
    const limpio = nombre.trim();
    if (!limpio) {
      toast.error("La lista necesita un nombre.");
      return;
    }
    if (vacio) {
      toast.info("Agregá equipos antes de guardar la lista.");
      return;
    }
    setBusy(true);
    try {
      await clienteApi.crearLista(limpio, items);
      toast.success(`Guardamos “${limpio}” en tus listas.`);
      setEditing(false);
      setNombre("");
    } catch (e) {
      toast.error((e as Error).message || "No se pudo guardar la lista.");
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
