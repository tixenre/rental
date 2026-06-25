import { useQuery } from "@tanstack/react-query";
import { fetchEntityMedia } from "@/lib/media/api";
import type { EntityMediaAsset } from "@/lib/media/types";

/**
 * Carga las variantes de media de una entidad desde /api/media/entity/{kind}/{entityId}.
 * Retorna [] si entityId es null/undefined (deshabilitado) — nunca undefined.
 */
export function useEntityMedia(
  kind: string,
  entityId: number | null | undefined,
): { data: EntityMediaAsset[]; isLoading: boolean; error: Error | null } {
  const result = useQuery({
    queryKey: ["media", "entity", kind, entityId],
    queryFn: () => fetchEntityMedia(kind, entityId!).then((r) => r.assets),
    enabled: !!entityId,
    staleTime: 5 * 60 * 1000,
    // Polling: si hay assets con derivación en curso, refetch cada 2s hasta que
    // todos estén ready. Se auto-desactiva cuando no hay ninguno pending.
    refetchInterval: (query) => {
      const assets = query.state.data;
      if (!assets) return false;
      const hasPending = assets.some((a) => a.status && a.status !== "ready");
      return hasPending ? 2000 : false;
    },
  });

  return {
    data: result.data ?? [],
    isLoading: result.isLoading,
    error: result.error as Error | null,
  };
}
