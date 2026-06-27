import { Clock } from "lucide-react";
import { Calendar } from "@/design-system/ui/calendar";

export type Sesion = { fecha: string; hora_inicio: number; hora_fin: number };

interface TallerCalendarioProps {
  sesiones: Sesion[];
  horario?: string;
}

function fmtHora(h: number): string {
  return `${h}:00`;
}

export function TallerCalendario({ sesiones, horario }: TallerCalendarioProps) {
  if (!sesiones || sesiones.length === 0) {
    if (!horario) return null;
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Clock className="h-4 w-4 shrink-0 text-rosa" />
        <span>{horario}</span>
      </div>
    );
  }

  const sorted = [...sesiones].sort((a, b) => a.fecha.localeCompare(b.fecha));
  const sesionDates = sorted.map((s) => new Date(s.fecha + "T12:00:00"));

  const defaultMonth = sesionDates[0];
  const lastDate = sesionDates[sesionDates.length - 1];
  const firstMonthKey = defaultMonth.getFullYear() * 12 + defaultMonth.getMonth();
  const lastMonthKey = lastDate.getFullYear() * 12 + lastDate.getMonth();
  const numberOfMonths = lastMonthKey > firstMonthKey ? 2 : 1;

  const allSameTimes =
    sorted.length > 0 &&
    sorted.every(
      (s) => s.hora_inicio === sorted[0].hora_inicio && s.hora_fin === sorted[0].hora_fin,
    );

  return (
    <div className="flex flex-col gap-4">
      <div className="pointer-events-none select-none">
        <Calendar
          defaultMonth={defaultMonth}
          numberOfMonths={numberOfMonths}
          modifiers={{ sesion: sesionDates }}
          modifiersClassNames={{
            sesion: "bg-rosa text-ink font-bold !opacity-100 rounded-md",
          }}
          locale="es-AR"
        />
      </div>

      <div className="flex items-start gap-2 text-sm text-muted-foreground">
        <Clock className="h-4 w-4 shrink-0 mt-0.5 text-rosa" />
        {allSameTimes ? (
          <span>
            {fmtHora(sorted[0].hora_inicio)} — {fmtHora(sorted[0].hora_fin)} hs
          </span>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {sorted.map((s) => {
              const d = new Date(s.fecha + "T12:00:00");
              const label = d.toLocaleDateString("es-AR", {
                weekday: "short",
                day: "numeric",
                month: "short",
              });
              return (
                <li key={s.fecha}>
                  <span className="text-ink/60">{label}:</span> {fmtHora(s.hora_inicio)} —{" "}
                  {fmtHora(s.hora_fin)} hs
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
