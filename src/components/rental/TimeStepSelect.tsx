import { cn } from "@/lib/utils";

const SLOTS: string[] = (() => {
  const out: string[] = [];
  for (let h = 0; h < 24; h++) {
    out.push(`${String(h).padStart(2, "0")}:00`);
    out.push(`${String(h).padStart(2, "0")}:30`);
  }
  return out;
})();

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

type Props = {
  value: string;
  onChange: (v: string) => void;
  className?: string;
  "aria-label"?: string;
};

export function TimeStepSelect({ value, onChange, className, ...rest }: Props) {
  const safe = snapTo30(value);
  return (
    <select
      value={safe}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "tabular-nums bg-transparent focus:outline-none focus-visible:ring-2 focus-visible:ring-amber/50 rounded-md cursor-pointer",
        className,
      )}
      aria-label={rest["aria-label"] ?? "Horario"}
    >
      {SLOTS.map((s) => (
        <option key={s} value={s}>
          {s}
        </option>
      ))}
    </select>
  );
}
