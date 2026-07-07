import { cn } from "@/lib/utils";
import { snapTo30 } from "@/lib/time-utils";

const SLOTS: string[] = (() => {
  const out: string[] = [];
  for (let h = 0; h < 24; h++) {
    out.push(`${String(h).padStart(2, "0")}:00`);
    out.push(`${String(h).padStart(2, "0")}:30`);
  }
  return out;
})();

const toMin = (t: string) => {
  const [h = 0, m = 0] = (t ?? "").split(":").map(Number);
  return h * 60 + m;
};

type Props = {
  value: string;
  onChange: (v: string) => void;
  className?: string;
  /** Limita los slots a la franja [min, max] inclusive (horarios habilitados). */
  min?: string;
  max?: string;
  "aria-label"?: string;
};

export function TimeStepSelect({ value, onChange, className, min, max, ...rest }: Props) {
  const safe = snapTo30(value);
  const lo = min ? toMin(min) : 0;
  const hi = max ? toMin(max) : 24 * 60;
  const slots = SLOTS.filter((s) => {
    const t = toMin(s);
    return t >= lo && t <= hi;
  });
  // Si el valor actual cae fuera de la franja, lo incluimos igual para no
  // perder la selección (el form lo valida/clampa al cambiar de día).
  const opts = slots.includes(safe) ? slots : [...slots, safe].sort((a, b) => toMin(a) - toMin(b));
  return (
    <select
      value={safe}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "tabular-nums bg-transparent focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/50 rounded-md cursor-pointer min-h-[44px] px-1",
        className,
      )}
      aria-label={rest["aria-label"] ?? "Horario"}
    >
      {opts.map((s) => (
        <option key={s} value={s}>
          {s}
        </option>
      ))}
    </select>
  );
}
