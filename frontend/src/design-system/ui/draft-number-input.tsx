import { useEffect, useState } from "react";
import { Input } from "./input";

/**
 * Input numérico con borrador local — no dispara `onCommit` en cada tecla.
 *
 * El anti-patrón que reemplaza: un input atado directo a un valor
 * autoritativo (server, o estado que lo espeja) cuyo `onChange` parsea y
 * reescribe ESE MISMO valor en cada tecla (típicamente con un fallback tipo
 * `parseInt(v || "1", 10)` para el string vacío). Efecto: el campo nunca
 * llega a mostrarse vacío el tiempo suficiente para escribir un número
 * nuevo — arrancando en "0", tipear "5" da "05" (el "0" nunca se termina
 * de borrar antes de que el valor lo vuelva a pisar); si además el commit
 * dispara una mutación de red que deshabilita el input mientras está en
 * vuelo, el campo se bloquea a mitad de edición. Encontrado primero en
 * `KitComponentEditor.tsx` (cantidad/descuento de kit y combo — reportado
 * en vivo por el dueño), confirmado con el mismo patrón en
 * `ContenidoIncluidoEditor.tsx`, `PedidoPageCards.tsx`/`PedidoPageHelpers.tsx`
 * y el stepper `QtyInput`.
 *
 * Acá se edita LIBRE en un string local (clear, tipear, lo que sea) sin
 * pegarle a `onCommit` en cada tecla; recién confirma al salir del campo o
 * con Enter. Si el valor no cambió, ni siquiera llama a `onCommit`. Se
 * resincroniza desde afuera (`value`) SOLO cuando el campo no está en
 * foco — no pisa una edición en curso.
 */
export function DraftNumberInput({
  value,
  onCommit,
  min,
  max,
  step,
  className,
  disabled,
  ariaLabel,
}: {
  value: number;
  onCommit: (v: number) => void;
  min: number;
  max?: number;
  step?: number | string;
  className?: string;
  disabled?: boolean;
  ariaLabel?: string;
}) {
  const [draft, setDraft] = useState(String(value));
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (!focused) setDraft(String(value));
  }, [value, focused]);

  const commit = () => {
    const parsed = parseFloat(draft.replace(",", "."));
    const clamped = Number.isFinite(parsed)
      ? Math.max(min, max != null ? Math.min(max, parsed) : parsed)
      : value;
    setDraft(String(clamped));
    if (clamped !== value) onCommit(clamped);
  };

  return (
    <Input
      type="number"
      min={min}
      max={max}
      step={step}
      value={draft}
      className={className}
      disabled={disabled}
      aria-label={ariaLabel}
      onFocus={() => setFocused(true)}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        setFocused(false);
        commit();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
      }}
    />
  );
}
