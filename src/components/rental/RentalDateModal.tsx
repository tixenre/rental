import { useMemo } from "react";
import { useCart } from "@/lib/cart-store";
import { DateRangePickerModal } from "./DateRangePickerModal";

type Props = {
  open: boolean;
  onOpenChange: (o: boolean) => void;
};

/**
 * Selector de fechas del carrito público — wrapper fino sobre
 * `DateRangePickerModal` (el core reusable y controlado por props), cableado al
 * `useCart`. Mantiene la firma `{ open, onOpenChange }` de sus 6 consumidores.
 *
 * Parity exacta del carrito: los setters del store (`setStartTime`/`setEndTime`)
 * ya hacen `snapTo30`; al pasarlos como callbacks ese comportamiento se mantiene.
 * `respectHorarios`/`!allowPast` reproducen las restricciones de horarios, días
 * pasados y stock que tenía el carrito.
 */
export function RentalDateModal({ open, onOpenChange }: Props) {
  const { items, startDate, endDate, startTime, endTime, setDates, setStartTime, setEndTime } =
    useCart();

  // Días bloqueados (sin stock): misma construcción de `itemsParam` que antes.
  const itemsParam = useMemo(
    () =>
      Object.entries(items)
        .filter(([id, qty]) => /^\d+$/.test(id) && qty > 0)
        .map(([id, qty]) => `${id}:${qty}`)
        .join(","),
    [items],
  );

  return (
    <DateRangePickerModal
      open={open}
      onOpenChange={onOpenChange}
      startDate={startDate}
      endDate={endDate}
      startTime={startTime}
      endTime={endTime}
      onDatesChange={setDates}
      onStartTimeChange={setStartTime}
      onEndTimeChange={setEndTime}
      options={{ respectHorarios: true, allowPast: false, itemsParam }}
    />
  );
}
