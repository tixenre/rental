import { type DateRange } from "react-day-picker";
import { es } from "date-fns/locale";
import { addDays, format, startOfDay } from "date-fns";
import { X } from "lucide-react";
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
        className="max-w-3xl p-0 gap-0 overflow-hidden bg-background flex flex-col h-[100dvh] sm:h-auto sm:max-h-[90dvh] sm:rounded-lg rounded-none"
      >
        <VisuallyHidden>
          <DialogTitle>Tu Rental — Seleccionar fechas</DialogTitle>
          <DialogDescription>
            Elegí la fecha de retiro y devolución del alquiler.
          </DialogDescription>
        </VisuallyHidden>

        {/* Header sticky */}
        <div
          className="flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4 border-b hairline shrink-0"
          style={{ paddingTop: "max(0.75rem, env(safe-area-inset-top))" }}
        >
          <h2 className="wordmark text-lg sm:text-xl text-foreground">Tu Rental</h2>
          <button
            onClick={() => onOpenChange(false)}
            className="grid h-9 w-9 place-items-center rounded-full hover:bg-muted transition"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Resumen Retiro / Devolución */}
        <div className="px-4 sm:px-6 pt-4 pb-2 grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] gap-3 sm:gap-4 sm:items-center shrink-0">
          <div className="flex flex-col">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground mb-1">
              Retiro
            </span>
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm sm:text-base font-semibold tabular-nums text-sky-600 border-b-2 border-sky-500 pb-0.5 px-1 bg-sky-50/60">
                {range?.from ? format(range.from, "dd-MM-yyyy") : "--/--/----"}
              </span>
              <TimeStepSelect
                value={startTime}
                onChange={setStartTime}
                aria-label="Hora de retiro"
                className="text-sm sm:text-base font-semibold text-rose-600 border-b-2 border-rose-500 pb-0.5 px-1"
              />
            </div>
          </div>

          <div className="hidden sm:block text-muted-foreground text-2xl text-center">→</div>

          <div className="flex flex-col">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground mb-1">
              Devolución
            </span>
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm sm:text-base font-semibold tabular-nums text-rose-600 border-b-2 border-rose-500 pb-0.5 px-1">
                {range?.to ? format(range.to, "dd-MM-yyyy") : "--/--/----"}
              </span>
              <TimeStepSelect
                value={endTime}
                onChange={setEndTime}
                aria-label="Hora de devolución"
                className="text-sm sm:text-base font-semibold text-rose-600 border-b-2 border-rose-500 pb-0.5 px-1"
              />
            </div>
          </div>
        </div>

        <p className="px-4 sm:px-6 pb-2 text-[11px] text-muted-foreground shrink-0">
          Horarios cada 30 min · sujeto a confirmación.
        </p>

        {/* Calendario — área scrolleable */}
        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain flex justify-center px-2 sm:px-4 pb-2">
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
            className="p-2 sm:p-3 pointer-events-auto"
          />
        </div>

        {/* Footer sticky con CTA siempre visible */}
        <div
          className="border-t hairline bg-surface px-4 sm:px-6 pt-3 pb-3 shrink-0 flex flex-col gap-2"
          style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}
        >
          {hasRange && (
            <div className="text-center font-mono text-[10px] sm:text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              {jornadas} {jornadas === 1 ? "jornada" : "jornadas"} · retiro {startTime} · devolución {endTime}
            </div>
          )}
          <div className="flex items-center justify-between gap-3">
            <button
              onClick={clear}
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition px-1 py-2"
            >
              <X className="h-3.5 w-3.5" />
              Limpiar
            </button>
            <button
              onClick={apply}
              className="flex-1 sm:flex-none rounded-full bg-amber px-6 py-3 sm:py-2.5 text-sm font-semibold text-ink hover:opacity-90 transition shadow-sm"
            >
              Aplicar
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
