/**
 * Utilidades de tiempo compartidas por TimeStepSelect y el carrito.
 *
 * Viven en su propio módulo (no en TimeStepSelect.tsx) para que el archivo del
 * componente exporte solo componentes y Fast Refresh funcione bien.
 */

/** Redondea un horario "HH:MM" al slot de 30 minutos más cercano, acotado a [00:00, 23:30]. */
export function snapTo30(value: string): string {
  const [hRaw, mRaw] = (value ?? "").split(":");
  const h = Math.min(23, Math.max(0, parseInt(hRaw ?? "0", 10) || 0));
  const m = Math.min(59, Math.max(0, parseInt(mRaw ?? "0", 10) || 0));
  const total = h * 60 + Math.round(m / 30) * 30;
  const clamped = Math.min(23 * 60 + 30, total);
  const hh = Math.floor(clamped / 60);
  const mm = clamped % 60;
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}
