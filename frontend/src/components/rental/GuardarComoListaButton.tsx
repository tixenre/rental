/**
 * GuardarComoListaButton.tsx — Control "Guardar como lista" (#1092) — CONTAINER.
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
 * - El gesto botón↔input vive en el shell `GuardarComoListaView` (fuente única,
 *   que también muestra la vitrina del DS con un onSave mock). Acá solo el cableado.
 */
import { toast } from "sonner";

import { clienteApi, type ListaItem } from "@/lib/cliente/api";
import { GuardarComoListaView } from "./GuardarComoListaView";

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
  const vacio = items.length === 0;

  async function onSave(nombre: string): Promise<boolean> {
    if (vacio) {
      toast.info("Agregá equipos antes de guardar la lista.");
      return false;
    }
    try {
      await clienteApi.crearLista(nombre, items);
      toast.success(`Guardamos “${nombre}” en tus listas.`);
      return true;
    } catch (e) {
      toast.error((e as Error).message || "No se pudo guardar la lista.");
      return false;
    }
  }

  return (
    <GuardarComoListaView
      onSave={onSave}
      disabled={vacio}
      className={className}
      placeholder={placeholder}
    />
  );
}
