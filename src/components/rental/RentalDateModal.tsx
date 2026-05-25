import { es } from "date-fns/locale";
import { addDays, format, startOfDay } from "date-fns";
import { X, Calendar as CalendarIcon, Clock, Eraser, Minus, Plus } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Calendar } from "@/components/ui/calendar";
import { useCart } from "@/lib/cart-store";
import { deriveEndDate, diaAbierto, franjaParaFecha } from "@/lib/rental-dates";
import { useHorarios } from "@/lib/horarios";
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

/**
 * Modal de fechas — patrón unificado con el mobile: elegís la fecha de retiro
 * y la cantidad de JORNADAS con un stepper; la devolución se calcula sola.
 *
 * El contador de jornadas es la fuente de verdad `days()` del carrito, que
 * coincide con el backend (1 jornada = 24 h; devolver más tarde que la hora
 * de retiro suma una jornada). El stepper mueve la fecha de devolución ±1 día.
 */
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
  const horarios = useHorarios();

  const today = startOfDay(new Date());
  const busy = buildBusyDays();

  // Franja habilitada según el día de retiro/devolución (misma config para
  // ambos). null = sin restricción → TimeStepSelect muestra todo el rango.
  const franjaRetiro = franjaParaFecha(horarios, startDate);
  const franjaDevolucion = franjaParaFecha(horarios, endDate);

  // Si al cambiar de día la hora queda fuera de la franja, la clampeamos al
  // inicio de la franja para no dejar una selección inválida.
  useEffect(() => {
    if (franjaRetiro && startTime < franjaRetiro.desde) setStartTime(franjaRetiro.desde);
    else if (franjaRetiro && startTime > franjaRetiro.hasta) setStartTime(franjaRetiro.hasta);
  }, [franjaRetiro, startTime, setStartTime]);
  useEffect(() => {
    if (franjaDevolucion && endTime < franjaDevolucion.desde) setEndTime(franjaDevolucion.desde);
    else if (franjaDevolucion && endTime > franjaDevolucion.hasta) setEndTime(franjaDevolucion.hasta);
  }, [franjaDevolucion, endTime, setEndTime]);

  // Setea la fecha de devolución para alcanzar `target` jornadas exactas
  // (deriveEndDate vive en el util compartido, espejo del backend).
  const setJornadas = (target: number, base?: Date) => {
    const start = base ?? startDate;
    if (!start) return;
    setDates(start, deriveEndDate(start, target, startTime, endTime));
  };

  // Al elegir la fecha de retiro preservamos las jornadas actuales (default 1).
  const handleStartSelect = (d: Date | undefined) => {
    if (!d) {
      setDates(undefined, undefined);
      return;
    }
    setJornadas(startDate && endDate ? jornadas : 1, d);
  };

  const incJornada = () => setJornadas(jornadas + 1);
  const decJornada = () => {
    if (jornadas <= 1) return;
    setJornadas(jornadas - 1);
  };

  const apply = () => onOpenChange(false);
  const clear = () => setDates(undefined, undefined);
  const hasStart = !!startDate;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideClose
        className="max-w-3xl p-0 gap-0 overflow-hidden bg-background flex flex-col h-[100dvh] sm:h-auto sm:max-h-[90dvh] sm:rounded-2xl rounded-none border-0 sm:border shadow-2xl"
      >
        <VisuallyHidden>
          <DialogTitle>Tu Rental — Seleccionar fechas</DialogTitle>
          <DialogDescription>
            Elegí la fecha de retiro y la cantidad de jornadas del alquiler.
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

        {/* Retiro + jornadas + devolución calculada */}
        <div className="px-5 sm:px-6 pt-5 pb-4 shrink-0 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Retiro */}
            <div className="rounded-xl border hairline bg-surface/40 px-3.5 py-3 border-ink/15">
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-1.5">
                Retiro
              </div>
              <div className="flex items-center justify-between gap-3">
                <span
                  className={`tabular-nums text-base font-display leading-none ${
                    startDate ? "text-ink" : "text-muted-foreground/50"
                  }`}
                >
                  {startDate ? format(startDate, "dd MMM yyyy", { locale: es }) : "--/--/----"}
                </span>
                <TimeStepSelect
                  value={startTime}
                  onChange={setStartTime}
                  min={franjaRetiro?.desde}
                  max={franjaRetiro?.hasta}
                  aria-label="Hora de retiro"
                  className="text-sm font-mono tabular-nums text-ink/80 hover:text-ink rounded-md px-2 py-1 bg-background border hairline"
                />
              </div>
            </div>

            {/* Jornadas stepper */}
            <div className="rounded-xl border border-ink/15 bg-amber-soft/40 px-3.5 py-3">
              <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-1.5">
                Jornadas
              </div>
              <div className="flex items-center justify-between gap-2">
                <button
                  onClick={decJornada}
                  disabled={!hasStart || jornadas <= 1}
                  aria-label="Quitar una jornada"
                  className="grid h-8 w-8 place-items-center rounded-full border hairline bg-background text-ink transition hover:border-ink disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <Minus className="h-4 w-4" />
                </button>
                <div className="flex items-baseline gap-1.5 leading-none">
                  <span className="font-display text-2xl font-black text-ink tabular-nums">
                    {hasStart ? jornadas : "—"}
                  </span>
                  <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-muted-foreground">
                    {jornadas === 1 ? "jornada" : "jornadas"}
                  </span>
                </div>
                <button
                  onClick={incJornada}
                  disabled={!hasStart}
                  aria-label="Agregar una jornada"
                  className="grid h-8 w-8 place-items-center rounded-full border hairline bg-background text-ink transition hover:border-ink hover:bg-amber disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Devolución calculada */}
          {startDate && endDate && (
            <div className="rounded-xl border border-amber/40 bg-amber-soft/60 px-3.5 py-3 flex items-center justify-between gap-3">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground mb-1">
                  Devolución
                </div>
                <span className="tabular-nums text-base font-display leading-none text-ink">
                  {format(endDate, "dd MMM yyyy", { locale: es })}
                </span>
              </div>
              <TimeStepSelect
                value={endTime}
                onChange={setEndTime}
                min={franjaDevolucion?.desde}
                max={franjaDevolucion?.hasta}
                aria-label="Hora de devolución"
                className="text-sm font-mono tabular-nums text-ink/80 hover:text-ink rounded-md px-2 py-1 bg-background border hairline"
              />
            </div>
          )}

          <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <Clock className="h-3 w-3" />
            Horarios cada 30 min — sujeto a confirmación. Devolver más tarde que la hora de
            retiro suma una jornada.
          </p>
        </div>

        {/* Calendario — elegís la fecha de retiro */}
        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain flex justify-center px-2 sm:px-4 pb-2 border-t hairline">
          <Calendar
            mode="single"
            selected={startDate}
            onSelect={handleStartSelect}
            numberOfMonths={isMobile ? 1 : 2}
            locale={es}
            disabled={(date: Date) => date < today || !diaAbierto(horarios, date)}
            modifiers={
              startDate && endDate
                ? { busy, rango: { from: startDate, to: endDate } }
                : { busy }
            }
            modifiersClassNames={{
              busy: "bg-amber/30 text-ink rounded-full",
              rango: "bg-amber-soft/70 text-ink",
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
            disabled={!hasStart}
            className="flex items-center gap-1.5 text-xs font-mono uppercase tracking-[0.2em] text-muted-foreground hover:text-ink transition px-2 py-2 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Eraser className="h-3.5 w-3.5" />
            Limpiar
          </button>

          {hasStart && endDate && (
            <div className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-[0.18em] text-ink">
              <CalendarIcon className="h-3.5 w-3.5" />
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
