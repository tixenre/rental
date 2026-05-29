import { useEffect, useMemo } from "react";
import { clienteApi } from "@/lib/cliente/api";
import { useFavoritesStore } from "@/lib/favorites-store";
import { useClienteSession } from "@/lib/iva";

/**
 * Hook de favoritos: combina el store local (Zustand + localStorage) con la
 * sincronización al backend cuando el cliente está logueado.
 *
 * - Sin login: funciona puramente en localStorage (igual que el carrito).
 * - Al hacer login: hace un merge de los IDs locales al servidor, luego
 *   recarga del servidor. La operación es secuencial para evitar race conditions.
 * - Cada toggle: actualiza local (optimistic) + llama al endpoint si logueado.
 */
export function useFavoritos() {
  const store = useFavoritesStore();
  const { data: session } = useClienteSession();

  useEffect(() => {
    if (!session?.id) return;
    const sync = async () => {
      if (store.items.length > 0) {
        await clienteApi.syncFavoritos(store.items).catch(console.warn);
      }
      const serverIds = await clienteApi.getFavoritos().catch(() => null);
      if (serverIds) store.setItems(serverIds);
    };
    sync();
    // Correr solo cuando cambia el id de sesión (login/logout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id]);

  // Set derivado para lookups O(1) — recalcular solo cuando items cambia
  const itemsSet = useMemo(() => new Set(store.items), [store.items]);

  const toggle = (id: string) => {
    const wasFav = itemsSet.has(id);
    store.toggle(id); // actualiza local + dispara toast
    if (session?.id) {
      if (wasFav) clienteApi.removeFavorito(id).catch(console.warn);
      else clienteApi.addFavorito(id).catch(console.warn);
    }
  };

  return {
    items: store.items,
    has: (id: string) => itemsSet.has(id),
    toggle,
    count: store.items.length,
    setItems: store.setItems,
  };
}
