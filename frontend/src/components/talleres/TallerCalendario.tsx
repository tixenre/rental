import { Clock } from "lucide-react";
import { es } from "date-fns/locale";
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

  return (
    <div className="flex flex-col gap-3">
      {/* Calendario en card con tinte rosa */}
      <div className="rounded-2xl bg-rosa/5 border border-rosa/20 overflow-hidden pointer-events-none select-none flex justify-center py-2">
        <Calendar
          locale={es}
          month={defaultMonth}
          numberOfMonths={numberOfMonths}
          modifiers={{ sesion: sesionDates }}
          modifiersClassNames={{
            sesion: "bg-rosa text-ink font-bold !opacity-100 rounded-full",
          }}
          className="[--cell-size:2.75rem]"
        />
      </div>

      {/* Píldoras de fecha + horario */}
      <div className="flex flex-col gap-2">
        {sorted.map((s) => {
          const d = new Date(s.fecha + "T12:00:00");
          const dayStr = d.toLocaleDateString("es-AR", {
            weekday: "long",
            day: "numeric",
            month: "long",
          });
          return (
            <div
              key={s.fecha}
              className="flex items-center gap-3 rounded-xl bg-muted/40 border border-border/50 px-4 py-3"
            >
              <div className="w-1 self-stretch rounded-full bg-rosa flex-none" />
              <div className="flex flex-col gap-0.5 min-w-0">
                <span className="font-semibold text-ink text-sm">
                  {dayStr.charAt(0).toUpperCase() + dayStr.slice(1)}
                </span>
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3 text-rosa flex-none" />
                  {fmtHora(s.hora_inicio)} — {fmtHora(s.hora_fin)} hs
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
