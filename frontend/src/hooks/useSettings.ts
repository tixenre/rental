/**
 * useSettings — hooks para leer settings globales de la app desde el cache
 * de TanStack Query. Centralizan el query key y el parsing de tipo.
 *
 * Las settings se exponen vía GET /api/settings/:key (lectura pública para
 * que el frontend no autenticado también pueda leerlas — ej. el USD rate
 * eventualmente puede mostrarse al cliente para conversión de precios).
 */
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/lib/admin/api";

const SETTINGS_STALE_MS = 5 * 60_000; // 5 min — el USD lo cambia el admin manualmente
const SETTINGS_CACHE_MS = 30 * 60_000; // 30 min retain

/** Tipo de cambio ARS por 1 USD. Default 1000 si falla la red.
 *  El componente que lo use puede mostrar un fallback hasta que cargue.
 *  `opts.staleTime`: override para call-sites admin (ver useEquipos()). */
export function useUsdRate(opts?: { staleTime?: number }): {
  rate: number;
  isLoading: boolean;
  updatedAt: string | null;
  updatedBy: string | null;
} {
  const q = useQuery({
    queryKey: ["settings", "usd_rate"],
    queryFn: () => adminApi.getSetting("usd_rate"),
    staleTime: opts?.staleTime ?? SETTINGS_STALE_MS,
    gcTime: SETTINGS_CACHE_MS,
    retry: 1,
  });
  const parsed = Number(q.data?.value);
  return {
    rate: Number.isFinite(parsed) && parsed > 0 ? parsed : 1000,
    isLoading: q.isLoading,
    updatedAt: q.data?.updated_at ?? null,
    updatedBy: q.data?.updated_by ?? null,
  };
}

/** ROI % default para nuevos equipos. Default 3. */
export function useRoiPctDefault(opts?: { staleTime?: number }): number {
  const q = useQuery({
    queryKey: ["settings", "roi_pct_default"],
    queryFn: () => adminApi.getSetting("roi_pct_default").catch(() => null),
    staleTime: opts?.staleTime ?? SETTINGS_STALE_MS,
    retry: 0,
  });
  const parsed = Number(q.data?.value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 3;
}

/** Lead-time: horas mínimas de antelación para que el cliente reserve online
 *  (#1126). Default 0 = apagado. El admin lo configura desde /admin/settings.
 *  El backend es la fuente de verdad (lo enforza el portero + el backstop de
 *  creación); el front lo lee solo para avisar antes de tiempo (disclaimer).
 *
 *  Expone también `ready` (¿ya resolvió la query, sea con éxito o con el
 *  catch-a-null?): mientras carga, `horas` cae al default 0 — indistinguible
 *  de "antelación apagada de verdad". Un consumidor que DERIVE un piso/clamp
 *  de este valor (no solo mostrarlo) tiene que esperar `ready`, o corre el
 *  riesgo de clampear con el 0 de arranque y quedarse con eso pisado incluso
 *  después de que llegue el valor real (visto en prod: date picker clampeaba
 *  la hora a "ahora" con el 0 inicial, y esa hora sobrevivía aunque el piso
 *  correcto —antelación real— corriera la FECHA para adelante después). */
export function useAntelacionMinimaHorasQuery(opts?: { staleTime?: number }): {
  horas: number;
  ready: boolean;
} {
  const q = useQuery({
    queryKey: ["settings", "antelacion_minima_horas"],
    queryFn: () => adminApi.getSetting("antelacion_minima_horas").catch(() => null),
    staleTime: opts?.staleTime ?? SETTINGS_STALE_MS,
    retry: 0,
  });
  const parsed = Number(q.data?.value);
  return {
    horas: Number.isFinite(parsed) && parsed > 0 ? parsed : 0,
    ready: !q.isLoading,
  };
}

export function useAntelacionMinimaHoras(opts?: { staleTime?: number }): number {
  return useAntelacionMinimaHorasQuery(opts).horas;
}

/** Helper puro: precio jornada en ARS según fórmula
 *    precio_usd × usd_rate × (roi_pct / 100)
 *  Devuelve null si falta algún input.
 *  El resultado se redondea al múltiplo de 100 más cercano (sin centavos
 *  ni unidades, que confunden al cliente: $1.184 → $1.200).
 */
export function calcularPrecioJornada(
  precio_usd: number | null | undefined,
  usd_rate: number | null | undefined,
  roi_pct: number | null | undefined,
): number | null {
  if (!precio_usd || !usd_rate || !roi_pct) return null;
  if (precio_usd <= 0 || usd_rate <= 0 || roi_pct <= 0) return null;
  const raw = precio_usd * usd_rate * (roi_pct / 100);
  return Math.round(raw / 100) * 100;
}
