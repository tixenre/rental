/**
 * queryClient.ts — instancia única de QueryClient de la app.
 *
 * Vive en un módulo propio (no en main.tsx, que monta la app al importarse)
 * para que código NO-componente (ej. `lib/iva.ts::invalidateClienteSession`)
 * pueda invalidar queries sin arrastrar el entrypoint completo.
 */
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      // Mantener datos "frescos" 30 segundos antes de re-fetchear.
      // Para datos que cambian con baja frecuencia (catálogo, categorías,
      // marcas) y querés que la navegación instantánea sea rápida.
      // Endpoints específicos pueden sobrescribir con staleTime propio
      // (ej. admin/pedidos.index.tsx con refetchInterval: 5000).
      staleTime: 30_000,
      // Mantener en caché 5 minutos después de que se quede sin observadores.
      // Mejora navegación back/forward.
      gcTime: 30 * 60_000,
    },
  },
});

// Back-office sin cache de frescura: pocos admins, prioridad total a ver el
// dato recién guardado sobre ahorrar un fetch (el público SÍ se beneficia de
// cachear, así que su staleTime de 30-60s queda intacto — ver hooks
// compartidos en useEquipos.ts/useSettings.ts, que exponen un override
// explícito para sus call-sites admin en vez de tocar el default público).
// setQueryDefaults matchea por PREFIJO — cubre toda query cuya key empiece
// con "admin" (la convención ya usada en absolutamente todo el back-office).
queryClient.setQueryDefaults(["admin"], { staleTime: 0 });
