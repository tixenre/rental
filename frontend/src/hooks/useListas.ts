import { useCallback, useEffect, useState } from "react";
import { clienteApi, type ListaItem, type ListaPersonal } from "@/lib/cliente/api";
import { useClienteSession } from "@/lib/iva";

/**
 * Hook de listas / kits personales (#1092). A diferencia de favoritos, las listas
 * son una acción logueada deliberada → server-only (sin store local ni sync de
 * localStorage). Este hook es la superficie de ADMINISTRACIÓN (la pestaña del
 * portal): trae todas las listas y expone las mutaciones.
 *
 * Las entradas "guardar como lista" (carrito / pedido) NO usan este hook —
 * llaman `clienteApi.crearLista` directo (one-shot), para no traer todas las
 * listas en superficies que solo crean una.
 *
 * El backend devuelve la lista completa en cada mutación → el estado local se
 * actualiza con esa respuesta (sin refetch).
 */
export function useListas() {
  const { data: session } = useClienteSession();
  const [listas, setListas] = useState<ListaPersonal[]>([]);
  const [loading, setLoading] = useState(false);

  const refetch = useCallback(async () => {
    if (!session?.id) {
      setListas([]);
      return;
    }
    setLoading(true);
    try {
      setListas(await clienteApi.getListas());
    } catch (e) {
      console.warn("getListas", e);
    } finally {
      setLoading(false);
    }
  }, [session?.id]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  const crear = useCallback(async (nombre: string, items: ListaItem[]) => {
    const nueva = await clienteApi.crearLista(nombre, items);
    setListas((prev) => [nueva, ...prev]);
    return nueva;
  }, []);

  const renombrar = useCallback(async (id: number, nombre: string) => {
    const upd = await clienteApi.renombrarLista(id, nombre);
    setListas((prev) => prev.map((l) => (l.id === id ? upd : l)));
    return upd;
  }, []);

  const quitarItem = useCallback(async (id: number, equipoId: number) => {
    const upd = await clienteApi.quitarItemLista(id, equipoId);
    setListas((prev) => prev.map((l) => (l.id === id ? upd : l)));
    return upd;
  }, []);

  const borrar = useCallback(async (id: number) => {
    await clienteApi.borrarLista(id);
    setListas((prev) => prev.filter((l) => l.id !== id));
  }, []);

  return { listas, loading, refetch, crear, renombrar, quitarItem, borrar };
}
