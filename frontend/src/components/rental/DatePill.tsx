import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Calendar as CalendarIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * DatePill — el pill central de fechas del rental (presentacional, fuente única).
 *
 * Es el SHELL del módulo de fechas: maneja solo presentación + el click; NO sabe
 * de `useCart`. El container (TopBar) lee el store y le pasa los valores; la
 * vitrina del DS le pasa estado mock para mostrarlo funcional sin tocar el carrito
 * real. Misma pieza en los dos lados → el diseño tiene una sola fuente de verdad.
 *
 * Estilado para el topbar de marca (fondo amber): hueso + ink. Mostralo sobre un
 * fondo de área para que se lea como en la app.
 */
export function DatePill({
  startDate,
  endDate,
  startTime,
  endTime,
  jornadas,
  onClick,
  className,
}: {
  startDate?: Date;
  endDate?: Date;
  startTime: string;
  endTime: string;
  jornadas: number;
  onClick: () => void;
  className?: string;
}) {
  const hasDates = !!(startDate && endDate);
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full border border-background/70 bg-background px-5 py-2 text-ink shadow-sm transition hover:bg-background/90",
        className,
      )}
      aria-label={hasDates ? "Editar fechas y horarios" : "Elegir fechas"}
    >
      <CalendarIcon className="h-4 w-4 shrink-0 text-amber" />
      {hasDates ? (
        <span className="truncate text-sm font-semibold tabular-nums">
          {format(startDate!, "EEE dd MMM", { locale: es })} {startTime}
          <span className="mx-1.5 opacity-50">→</span>
          {format(endDate!, "EEE dd MMM", { locale: es })} {endTime}
          <span className="ml-2 font-mono text-2xs uppercase tracking-wider text-ink/60">
            · {jornadas} {jornadas === 1 ? "jornada" : "jornadas"}
          </span>
        </span>
      ) : (
        <span className="text-sm font-semibold">Elegir fechas</span>
      )}
    </button>
  );
}
