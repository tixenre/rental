/**
 * business.ts — Datos del negocio (single source of truth).
 *
 * El teléfono es configurable desde `/admin/diseno` (setting
 * `whatsapp_phone`). El valor hardcoded acá es FALLBACK por si la setting
 * no está cargada o falla el fetch.
 */

import { useQuery } from "@tanstack/react-query";

/** Fallback hardcoded. El admin puede sobreescribirlo desde /admin/diseno. */
const FALLBACK_PHONE = "+5492235852510";

/** @deprecated Usar `useBusinessPhone()` para tomar el valor de settings.
 *  Sólo dejá esto para componentes que no pueden usar hooks (SSR, etc.). */
export const BUSINESS_PHONE = FALLBACK_PHONE;

/**
 * Hook que devuelve el teléfono del negocio leyendo el setting público.
 * Si la setting no existe o falla el fetch, cae al fallback hardcoded.
 * Cacheado por TanStack Query — un solo fetch por sesión.
 */
export function useBusinessPhone(): string {
  const q = useQuery({
    queryKey: ["settings", "whatsapp_phone"],
    queryFn: async () => {
      const res = await fetch("/api/settings/whatsapp_phone");
      if (!res.ok) return FALLBACK_PHONE;
      const data = await res.json();
      return (data?.value as string) || FALLBACK_PHONE;
    },
    staleTime: 5 * 60 * 1000, // 5 min
  });
  return q.data ?? FALLBACK_PHONE;
}
