import { useEffect, useState } from "react";
import { DayPicker, type DateRange } from "react-day-picker";
import { es } from "date-fns/locale";
import { addDays, format, startOfDay } from "date-fns";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { useCart } from "@/lib/cart-store";
import { cn } from "@/lib/utils";

type Props = {
  open: boolean;
  onOpenChange: (o: boolean) => void;
};

// Mock de días "ocupados" para demo visual (hasta tener backend)
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

  // Live: cualquier cambio se refleja al instante en el carrito
  const handleRangeChange = (r: DateRange | undefined) => {
    setDates(r?.from, r?.to);
  };

  const apply = () => onOpenChange(false);
  const clear = () => setDates(undefined, undefined);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-3xl p-0 gap-0 overflow-hidden bg-background border hairline [&>button[aria-label='Close']]:hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b hairline">
          <h2 className="wordmark text-xl text-foreground">Tu Rental</h2>
          <button
            onClick={() => onOpenChange(false)}
            className="rounded-full p-1.5 hover:bg-muted transition"
            aria-label="Cerrar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

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
        <div className="px-4 pb-2 overflow-x-auto">
          <DayPicker
            mode="range"
            selected={range}
            onSelect={handleRangeChange}
            numberOfMonths={2}
            locale={es}
            disabled={{ before: today }}
            modifiers={{ busy, available: (d) => d >= today && !busy.some((b) => b.getTime() === d.getTime()) }}
            showOutsideDays={false}
            className={cn("p-3 pointer-events-auto rdp-rambla")}
            classNames={{
              months: "flex gap-8 justify-center",
              month: "space-y-3",
              caption: "flex justify-center relative items-center h-9",
              caption_label: "text-sm font-semibold",
              nav: "flex items-center gap-1",
              nav_button:
                "h-7 w-7 inline-flex items-center justify-center rounded hover:bg-muted",
              nav_button_previous: "absolute left-1",
              nav_button_next: "absolute right-1",
              table: "w-full border-collapse",
              head_row: "flex",
              head_cell:
                "w-10 text-[10px] uppercase tracking-wider text-muted-foreground font-medium",
              row: "flex w-full mt-1",
              cell: "w-10 h-10 p-0 relative",
              day: "h-10 w-10 p-0 font-medium text-sm",
            }}
            components={{
              Chevron: ({ orientation }) =>
                orientation === "left" ? (
                  <ChevronLeft className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                ),
            }}
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
