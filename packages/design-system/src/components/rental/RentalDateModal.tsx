import { X, Calendar } from "lucide-react";
import { useState } from "react";
import { DayPicker, type DateRange } from "react-day-picker";
import { format, differenceInCalendarDays } from "date-fns";
import { es } from "date-fns/locale";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/lib/utils";

/**
 * RentalDateModal — modal de selección de rango de fechas.
 *
 * Usa react-day-picker en modo "range". El calendatio respeta los
 * modificadores de stock del sistema:
 *   - nostock:  fechas bloqueadas por falta de stock del equipo seleccionado.
 *              Se muestran con línea diagonal y color rojo suave.
 *   - closed:   fechas cerradas (feriados, mantenimiento).
 *              Se muestran en gris, no seleccionables.
 *
 * Los estilos de DayPicker se aplican vía classNames (Tailwind).
 * Ver `src/styles/rdp.css` para los overrides de `.rdp-rambla`.
 *
 * Animación entry: opacity + y 12px + scale 0.97 → 0, ease [0.32,0.72,0,1] 250ms.
 *
 * Formato de salida: DateRange { from: Date, to: Date }.
 * El padre convierte a string con formatRentalRange() de @/lib/format.
 *
 * Source visual: `preview/components-daterangepicker.html`
 *               + `uploads/rental-date-modal-states.html`
 */

export interface RentalDateModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (range: DateRange) => void;
  initialRange?: DateRange;
  noStockDates?: Date[];
  closedDates?: Date[];
}

export function RentalDateModal({
  open,
  onClose,
  onConfirm,
  initialRange,
  noStockDates = [],
  closedDates = [],
}: RentalDateModalProps) {
  const [range, setRange] = useState<DateRange | undefined>(initialRange);

  const jornadas = range?.from && range?.to ? differenceInCalendarDays(range.to, range.from) : 0;

  const rangeLabel =
    range?.from && range?.to
      ? `${format(range.from, "EEE d MMM.", { locale: es })} → ${format(range.to, "EEE d MMM.", { locale: es })}`
      : null;

  const handleConfirm = () => {
    if (range?.from && range?.to) {
      onConfirm(range);
      onClose();
    }
  };

  const canConfirm = Boolean(range?.from && range?.to && jornadas >= 1);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Scrim */}
          <motion.div
            key="rdm-scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            aria-hidden
            className="fixed inset-0 z-[var(--z-scrim)] bg-ink/40 backdrop-blur-sm"
          />

          {/* Modal */}
          <motion.div
            key="rdm-modal"
            role="dialog"
            aria-label="Seleccionar fechas de alquiler"
            aria-modal="true"
            initial={{ opacity: 0, y: 12, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.97 }}
            transition={{ ease: [0.32, 0.72, 0, 1], duration: 0.25 }}
            className={cn(
              "fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2",
              "z-[calc(var(--z-scrim)+1)]",
              "w-full max-w-[340px]",
              "rounded-2xl bg-surface-elevated shadow-[var(--shadow-xl)]",
              "overflow-hidden",
            )}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-hairline px-5 py-4">
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-amber" />
                <h2 className="text-base font-bold text-ink">Elegí tus fechas</h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Cerrar"
                className="grid h-7 w-7 place-items-center rounded-full border border-hairline text-muted-foreground transition-colors hover:text-ink"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Calendario */}
            <div className="p-4 rdp-rambla-wrapper">
              <DayPicker
                mode="range"
                selected={range}
                onSelect={setRange}
                locale={es}
                numberOfMonths={1}
                disabled={[{ before: new Date() }, ...closedDates, ...noStockDates]}
                modifiers={{
                  nostock: noStockDates,
                  closed: closedDates,
                }}
                modifiersClassNames={{
                  nostock: "rdp-day-nostock",
                  closed: "rdp-day-closed",
                }}
                showOutsideDays={false}
                fixedWeeks
              />
            </div>

            {/* Leyenda */}
            <div className="flex items-center gap-4 px-5 pb-2">
              <div className="flex items-center gap-1.5">
                <div className="h-3 w-3 rounded-full bg-destructive/15 border border-destructive/30" />
                <span className="font-mono text-[9px] uppercase tracking-[0.08em] text-muted-foreground">
                  Sin stock
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="h-3 w-3 rounded-full bg-surface border border-hairline opacity-50" />
                <span className="font-mono text-[9px] uppercase tracking-[0.08em] text-muted-foreground">
                  Cerrado
                </span>
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between gap-3 border-t border-hairline px-5 py-4">
              <div className="min-w-0">
                {rangeLabel ? (
                  <>
                    <p className="text-sm font-semibold text-ink truncate">{rangeLabel}</p>
                    <p className="font-mono text-[10px] text-muted-foreground">
                      {jornadas} {jornadas === 1 ? "jornada" : "jornadas"}
                    </p>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">Seleccioná inicio y fin.</p>
                )}
              </div>
              <button
                type="button"
                onClick={handleConfirm}
                disabled={!canConfirm}
                className={cn(
                  "flex-shrink-0 rounded-full px-5 py-2",
                  "font-sans text-sm font-bold",
                  "bg-ink text-background",
                  "transition-all duration-[var(--duration-base)]",
                  "hover:bg-amber hover:text-ink",
                  "active:scale-[0.97]",
                  "disabled:opacity-40 disabled:pointer-events-none",
                )}
              >
                Confirmar
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
