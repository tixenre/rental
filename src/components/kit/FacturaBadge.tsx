import { cn } from "@/lib/utils";
import type { FacturaEstado } from "@/lib/admin/api";

const FACTURA_MAP: Record<FacturaEstado, { label: string; cls: string }> = {
  pendiente: {
    label: "Pendiente",
    cls: "bg-amber/15 text-ink border-amber/50",
  },
  emitida: {
    label: "Emitida",
    cls: "bg-verde/10 text-verde border-verde/30",
  },
  error: {
    label: "Error",
    cls: "bg-destructive/10 text-destructive border-destructive/30",
  },
  anulada: {
    label: "Anulada",
    cls: "bg-muted text-muted-foreground border-hairline",
  },
};

export function FacturaBadge({
  estado,
  className,
}: {
  estado: FacturaEstado | string;
  className?: string;
}) {
  const { label, cls } = FACTURA_MAP[estado as FacturaEstado] ?? {
    label: estado,
    cls: "bg-muted text-muted-foreground border-transparent",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 font-sans text-[10px] font-medium",
        cls,
        className,
      )}
    >
      {label}
    </span>
  );
}
