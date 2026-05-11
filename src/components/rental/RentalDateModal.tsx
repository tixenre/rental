import { type DateRange } from "react-day-picker";
import { es } from "date-fns/locale";
import { addDays, format, startOfDay } from "date-fns";
import { X, ArrowRight, Calendar as CalendarIcon, Clock, Eraser } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Calendar } from "@/components/ui/calendar";
import { useCart } from "@/lib/cart-store";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import { TimeStepSelect } from "./TimeStepSelect";
import { useEffect, useState } from "react";

type Props = {
  open: boolean;
  onOpenChange: (o: boolean) => void;
};

function buildBusyDays(): Date[] {
  const today = startOfDay(new Date());
  return [addDays(today, 5), addDays(today, 12), addDays(today, 13), addDays(today, 27)];
}

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 639px)");
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return isMobile;
}

export function RentalDateModal({ open, onOpenChange }: Props) {
  const {
    startDate,
    endDate,
    startTime,
    endTime,
    setDates,
    setStartTime,
    setEndTime,
    days,
  } = useCart();
  const jornadas = days();
  const isMobile = useIsMobile();

  const range: DateRange | undefined = startDate
    ? { from: startDate, to: endDate }
    : undefined;

  const today = startOfDay(new Date());
  const busy = buildBusyDays();

  const handleRangeChange = (r: DateRange | undefined) => {
    setDates(r?.from, r?.to);
  };

  const apply = () => onOpenChange(false);
  const clear = () => setDates(undefined, undefined);
  const hasRange = !!(range?.from && range?.to);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="max-w-3xl p-0 gap-0 overflow-hidden bg-background flex flex-col h-[100dvh] sm:h-auto sm:max-h-[90dvh] sm:rounded-2xl rounded-none border-0 sm:border shadow-2xl"
      >
        <VisuallyHidden>
          <DialogTitle>Tu Rental — Seleccionar fechas</DialogTitle>
          <DialogDescription>
            Elegí la fecha de retiro y devolución del alquiler.
          </DialogDescription>
        </VisuallyHidden>

        {/* Header */}
        <div
          className="flex items-center justify-between px-5 sm:px-6 py-4 border-b hairline shrink-0 bg-surface/30"
          style={{ paddingTop: "max(1rem, env(safe-area-inset-top))" }}
        >
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
              Fechas del alquiler
            </div>
            <h2 className="font-display text-xl sm:text-2xl text-ink leading-tight">
              Elegí tus fechas
            </h2>
          </div>
          <button
            onClick={() => onOpenChange(false)}
            className="grid h-9 w-9 place-items-center rounded-full hover:bg-muted transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Resumen Retiro / Devolución — diseño limpio */}
        <div className="px-5 sm:px-6 pt-5 pb-4 shrink-0">
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] gap-3 sm:gap-2 sm:items-stretch">
            <DateField
              label="Retiro"
              date={range?.from}
              time={startTime}
              onTimeChange={setStartTime}
              timeAriaLabel="Hora de retiro"
            />

            <div className="hidden sm:flex items-center justify-center text-muted-foreground/40 px-1">
              <ArrowRight className="h-4 w-4" />
            </div>
            <div className="sm:hidden flex items-center justify-center py-1">
              <div className="h-px flex-1 bg-border" />
              <ArrowRight className="h-3 w-3 mx-3 text-muted-foreground/50 rotate-90" />
              <div className="h-px flex-1 bg-border" />
            </div>

            <DateField
              label="Devolución"
              date={range?.to}
              time={endTime}
              onTimeChange={setEndTime}
              timeAriaLabel="Hora de devolución"
            />
          </div>

          <p className="mt-3 flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <Clock className="h-3 w-3" />
            Horarios cada 30 min — sujeto a confirmación
          </p>
        </div>

        {/* Calendario — área scrolleable */}
        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain flex justify-center px-2 sm:px-4 pb-2 border-t hairline">
          <Calendar
            mode="range"
            selected={range}
            onSelect={handleRangeChange}
            numberOfMonths={isMobile ? 1 : 2}
            locale={es}
            disabled={{ before: today }}
            modifiers={{ busy }}
            modifiersClassNames={{
              busy: "bg-amber/30 text-ink rounded-full",
            }}
            showOutsideDays={false}
            className="p-2 sm:p-4 pointer-events-auto"
          />
        </div>

        {/* Footer */}
        <div
          className="border-t hairline bg-surface/50 px-5 sm:px-6 pt-3 pb-3 shrink-0 flex items-center justify-between gap-3"
          style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}
        >
          <button
            onClick={clear}
            disabled={!hasRange && !startDate}
            className="flex items-center gap-1.5 text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground hover:text-ink transition px-2 py-2 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Eraser className="h-3.5 w-3.5" />
            Limpiar
          </button>

          {hasRange && (
            <div className="hidden sm:flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              <CalendarIcon className="h-3 w-3" />
              {jornadas} {jornadas === 1 ? "jornada" : "jornadas"}
            </div>
          )}

          <button
            onClick={apply}
            className="rounded-full bg-amber px-6 py-2.5 sm:py-2 text-sm font-semibold text-ink hover:brightness-110 transition shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
          >
            Aplicar
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Campo de fecha + hora con styling consistente y sin gritar visualmente. */
function DateField({
  label,
  date,
  time,
  onTimeChange,
  timeAriaLabel,
}: {
  label: string;
  date?: Date;
  time: string;
  onTimeChange: (t: string) => void;
  timeAriaLabel: string;
}) {
  const hasDate = !!date;
  return (
    <div
      className={`rounded-xl border hairline bg-surface/40 px-3.5 py-3 transition ${
        hasDate ? "border-ink/15" : ""
      }`}
    >
      <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-1.5">
        {label}
      </div>
      <div className="flex items-center justify-between gap-3">
        <span
          className={`tabular-nums text-base font-display leading-none ${
            hasDate ? "text-ink" : "text-muted-foreground/50"
          }`}
        >
          {date ? format(date, "dd MMM yyyy", { locale: es }) : "--/--/----"}
        </span>
        <TimeStepSelect
          value={time}
          onChange={onTimeChange}
          aria-label={timeAriaLabel}
          className="text-sm font-mono tabular-nums text-ink/80 hover:text-ink rounded-md px-2 py-1 bg-background border hairline"
        />
      </div>
    </div>
  );
}
