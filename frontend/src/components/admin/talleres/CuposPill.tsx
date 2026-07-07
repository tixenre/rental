import { Pill, type PillTone } from "@/design-system/ui/Pill";

export function CuposPill({ confirmados, total }: { confirmados: number; total: number }) {
  const ratio = total > 0 ? confirmados / total : 0;
  const tone: PillTone = ratio >= 1 ? "danger" : ratio >= 0.8 ? "warning" : "success";
  return (
    <Pill tone={tone} className="font-mono font-semibold tabular-nums">
      {confirmados}/{total}
    </Pill>
  );
}
