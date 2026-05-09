import { type DateRange } from "react-day-picker";
import { es } from "date-fns/locale";
import { addDays, format, startOfDay } from "date-fns";
import { X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Calendar } from "@/components/ui/calendar";
import { useCart } from "@/lib/cart-store";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";

type Props = {
  open: boolean;
  onOpenChange: (o: boolean) => void;
};

function buildBusyDays(): Date[] {
  const today = startOfDay(new Date());
  return [addDays(today, 5), addDays(today, 12), addDays(today, 13), addDays(today, 27)];
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
  } = useCart();

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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl p-0 gap-0 overflow-hidden bg-background">
        <VisuallyHidden>
          <DialogTitle>Tu Rental — Seleccionar fechas</DialogTitle>
          <DialogDescription>
            Elegí la fecha de inicio y devolución del alquiler.
          </DialogDescription>
        </VisuallyHidden>

        {/* Header */}
        <DialogHeader className="flex flex-row items-center justify-between px-6 py-4 border-b hairline space-y-0">
          <h2 className="wordmark text-xl text-foreground">Tu Rental</h2>
        </DialogHeader>

        {/* Resumen Inicio / Devolver */}
        <div className="px-6 pt-5 pb-3 flex items-center justify-between gap-4">
          <div className="flex flex-col">
            <span className="text-xs font-medium text-foreground mb-1">Inicio</span>
            <div className="flex items-center gap-3">
              <span className="text-base font-semibold tabular text-sky-600 border-b-2 border-sky-500 pb-0.5 px-1 bg-sky-50/60">
                {range?.from ? format(range.from, "dd-MM-yyyy") : "--/--/----"}
              </span>
              <input
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                className="text-base font-semibold tabular text-rose-600 border-b-2 border-rose-500 pb-0.5 px-1 bg-transparent focus:outline-none"
              />
            </div>
          </div>

          <div className="text-muted-foreground text-2xl">→</div>

          <div className="flex flex-col items-end">
            <span className="text-xs font-medium text-foreground mb-1">Devolver</span>
            <div className="flex items-center gap-3">
              <span className="text-base font-semibold tabular text-rose-600 border-b-2 border-rose-500 pb-0.5 px-1">
                {range?.to ? format(range.to, "dd-MM-yyyy") : "--/--/----"}
              </span>
              <input
                type="time"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                className="text-base font-semibold tabular text-rose-600 border-b-2 border-rose-500 pb-0.5 px-1 bg-transparent focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Calendario doble */}
        <div className="flex justify-center px-4 pb-2">
          <Calendar
            mode="range"
            selected={range}
            onSelect={handleRangeChange}
            numberOfMonths={2}
            locale={es}
            disabled={{ before: today }}
            modifiers={{ busy }}
            modifiersClassNames={{
              busy: "bg-amber/30 text-ink rounded-full",
            }}
            showOutsideDays={false}
            className="p-3 pointer-events-auto"
          />
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t hairline flex items-center justify-between bg-surface">
          <button
            onClick={clear}
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition"
          >
            <X className="h-3.5 w-3.5" />
            Limpiar fechas
          </button>
          <button
            onClick={apply}
            className="rounded-full bg-amber px-6 py-2.5 text-sm font-semibold text-ink hover:opacity-90 transition shadow-sm"
          >
            Aplicar
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
