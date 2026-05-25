/**
 * Horarios habilitados de retiro/devolución — lectura del setting público
 * `horarios_retiro` (JSON). Si no está configurado, devuelve null = sin
 * restricción (todo abierto, comportamiento previo).
 */
import { useQuery } from "@tanstack/react-query";
import { parseHorarios, type HorariosSemana } from "@/lib/rental-dates";

export const HORARIOS_SETTING_KEY = "horarios_retiro";

export function useHorarios(): HorariosSemana | null {
  const q = useQuery({
    queryKey: ["settings", HORARIOS_SETTING_KEY],
    queryFn: async () => {
      const res = await fetch(`/api/settings/${HORARIOS_SETTING_KEY}`);
      if (!res.ok) return null;
      const data = await res.json();
      return parseHorarios(data?.value as string | undefined);
    },
    staleTime: 5 * 60 * 1000,
  });
  return q.data ?? null;
}
