import { useMemo, useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import {
  Calendar as CalendarIcon,
  Minus,
  Plus,
  MessageCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { formatARS } from "@/lib/format";
import { STUDIO, STUDIO_PHONE, studioTotal } from "@/data/studio";

function pad(n: number) {
  return n.toString().padStart(2, "0");
}

function buildTimeSlots() {
  const slots: { value: string; label: string; hour: number; minute: 0 | 30 }[] = [];
  for (let h = STUDIO.openHour; h < STUDIO.closeHour; h++) {
    for (const m of [0, 30] as const) {
      slots.push({
        value: `${pad(h)}:${pad(m)}`,
        label: `${pad(h)}:${pad(m)}`,
        hour: h,
        minute: m,
      });
    }
  }
  return slots;
}

export function StudioBookingForm() {
  const [date, setDate] = useState<Date | undefined>(undefined);
  const [startSlot, setStartSlot] = useState<string>(`${pad(STUDIO.openHour)}:00`);
  const [hours, setHours] = useState<number>(STUDIO.minHours);
  const [withAddon, setWithAddon] = useState<boolean>(false);

  const slots = useMemo(buildTimeSlots, []);
  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const total = studioTotal({ durationHours: hours, withAddon });
  const subtotal = STUDIO.pricePerHour * hours;
  const slot = slots.find((s) => s.value === startSlot)!;

  const dateLabel = date
    ? format(date, "EEEE d 'de' MMMM, yyyy", { locale: es })
    : "Elegir fecha";

  const canSend = !!date;

  const handleWhatsapp = () => {
    if (!date) return;
    const start = `${pad(slot.hour)}:${pad(slot.minute)}`;
    const endTotalMin = slot.hour * 60 + slot.minute + hours * 60;
    const endH = Math.floor(endTotalMin / 60) % 24;
    const endM = endTotalMin % 60;
    const end = `${pad(endH)}:${pad(endM)}`;

    const lines = [
      `Hola! Quiero reservar el estudio.`,
      `📅 ${format(date, "EEEE d 'de' MMMM, yyyy", { locale: es })}`,
      `🕒 ${start} – ${end} (${hours} h)`,
      withAddon ? `➕ ${STUDIO.addon.name}` : null,
      total > 0 ? `💵 Total estimado: ${formatARS(total)}` : null,
    ].filter(Boolean);

    const text = encodeURIComponent(lines.join("\n"));
    window.open(`https://wa.me/${STUDIO_PHONE}?text=${text}`, "_blank");
  };

  return (
    <div className="rounded-2xl border hairline bg-surface p-5 sm:p-6">
      <div className="grid gap-5 lg:grid-cols-[1fr_auto_1fr] lg:gap-8">
        {/* Inputs */}
        <div className="space-y-4">
          {/* Fecha */}
          <div>
            <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Fecha
            </label>
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  className={cn(
                    "mt-1.5 w-full justify-start text-left font-normal",
                    !date && "text-muted-foreground",
                  )}
                >
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  <span className="capitalize">{dateLabel}</span>
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={date}
                  onSelect={setDate}
                  disabled={{ before: today }}
                  initialFocus
                  locale={es}
                  className={cn("p-3 pointer-events-auto")}
                />
              </PopoverContent>
            </Popover>
          </div>

          {/* Hora inicio */}
          <div>
            <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Hora de inicio
            </label>
            <select
              value={startSlot}
              onChange={(e) => setStartSlot(e.target.value)}
              className="mt-1.5 w-full rounded-md border hairline bg-background px-3 py-2 text-sm focus:border-amber/60 focus:outline-none"
            >
              {slots.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>

          {/* Duración */}
          <div>
            <label className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Duración (mín. {STUDIO.minHours} h)
            </label>
            <div className="mt-1.5 flex items-center gap-3 rounded-md border hairline bg-background px-2 py-1.5">
              <button
                type="button"
                onClick={() => setHours((h) => Math.max(STUDIO.minHours, h - 1))}
                className="flex h-8 w-8 items-center justify-center rounded-md border hairline text-muted-foreground hover:border-ink hover:text-ink disabled:opacity-40"
                disabled={hours <= STUDIO.minHours}
                aria-label="Restar hora"
              >
                <Minus className="h-4 w-4" />
              </button>
              <div className="flex-1 text-center text-base font-semibold tabular">
                {hours} <span className="text-sm font-normal text-muted-foreground">h</span>
              </div>
              <button
                type="button"
                onClick={() => setHours((h) => Math.min(12, h + 1))}
                className="flex h-8 w-8 items-center justify-center rounded-md border hairline text-muted-foreground hover:border-ink hover:text-ink"
                aria-label="Sumar hora"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Divider */}
        <div className="hidden lg:block w-px bg-border" />

        {/* Addon + resumen */}
        <div className="space-y-4">
          <label
            className={cn(
              "flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition",
              withAddon
                ? "border-amber bg-amber/10"
                : "hairline hover:border-ink",
            )}
          >
            <Checkbox
              checked={withAddon}
              onCheckedChange={(v) => setWithAddon(v === true)}
              className="mt-0.5"
            />
            <div className="flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <div className="font-semibold">{STUDIO.addon.name}</div>
                <div className="font-mono text-sm tabular">
                  {STUDIO.addon.pricePerDay > 0
                    ? `+${formatARS(STUDIO.addon.pricePerDay)}/día`
                    : "Consultar"}
                </div>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {STUDIO.addon.description}
              </p>
            </div>
          </label>

          <div className="rounded-xl bg-foreground p-4 text-background">
            <div className="flex items-center justify-between text-xs text-background/70">
              <span>Estudio · {hours} h</span>
              <span className="tabular">
                {subtotal > 0 ? formatARS(subtotal) : "—"}
              </span>
            </div>
            {withAddon && (
              <div className="mt-1 flex items-center justify-between text-xs text-background/70">
                <span>{STUDIO.addon.name}</span>
                <span className="tabular">
                  {STUDIO.addon.pricePerDay > 0
                    ? formatARS(STUDIO.addon.pricePerDay)
                    : "—"}
                </span>
              </div>
            )}
            <div className="mt-3 flex items-end justify-between border-t border-background/15 pt-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-background/60">
                Total estimado
              </span>
              <span className="text-2xl font-semibold tabular">
                {total > 0 ? formatARS(total) : "A consultar"}
              </span>
            </div>
          </div>

          <Button
            onClick={handleWhatsapp}
            disabled={!canSend}
            className="w-full bg-amber text-ink hover:bg-amber/90"
            size="lg"
          >
            <MessageCircle className="mr-2 h-4 w-4" />
            Reservar por WhatsApp
          </Button>
          {!canSend && (
            <p className="text-center text-xs text-muted-foreground">
              Elegí una fecha para continuar.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
