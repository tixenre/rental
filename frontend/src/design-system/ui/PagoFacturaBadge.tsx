import { Receipt } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * PagoFacturaBadge — micro-tags para marcar un pedido como Pagado y/o Facturado
 * sin ocupar espacio (la lista de pedidos es densa).
 *
 *  - Pagado    → círculo VERDE con "$" (se lee como plata cobrada).
 *  - Facturado → círculo VIOLETA con recibo (documento fiscal emitido).
 *  - Ambos     → UN solo óvalo partido al medio (mitad verde $ / mitad violeta
 *                recibo), en vez de dos círculos — no suma ancho.
 *  - Ninguno   → `null` (no renderiza nada).
 *
 * Complementa —no reemplaza— `PagoBadge`: ese muestra "Debe $X" cuando FALTA
 * cobrar; este marca los hitos YA cumplidos. El violeta es un token propio
 * (`--color-violeta`), sello administrativo aparte de los colores de estado.
 *
 * El detalle ("Pagado $296.611", "Factura A #123") va en el tooltip nativo +
 * `aria-label` — sin depender de un TooltipProvider en la superficie que lo use.
 */

const RECIBO = <Receipt className="h-3 w-3" aria-hidden />;

export function PagoFacturaBadge({
  pagado,
  facturado,
  className,
  detallePago,
  detalleFactura,
}: {
  pagado: boolean;
  facturado: boolean;
  className?: string;
  /** Texto del tooltip/aria del lado pago (ej. "Pagado $296.611"). */
  detallePago?: string;
  /** Texto del tooltip/aria del lado factura (ej. "Factura A #123"). */
  detalleFactura?: string;
}) {
  if (!pagado && !facturado) return null;

  const lblPago = detallePago ?? "Pagado";
  const lblFactura = detalleFactura ?? "Facturado";

  // Ambos → óvalo partido al medio (una sola pieza, sin sumar ancho).
  if (pagado && facturado) {
    const label = `${lblPago} · ${lblFactura}`;
    return (
      <span
        className={cn(
          "inline-flex h-[18px] items-stretch overflow-hidden rounded-full border border-ink/20 align-middle",
          className,
        )}
        title={label}
        aria-label={label}
      >
        <span
          className="inline-flex w-5 items-center justify-center bg-verde/15 text-2xs font-extrabold text-verde-ink"
          aria-hidden
        >
          $
        </span>
        <span
          className="inline-flex w-5 items-center justify-center border-l border-background/70 bg-violeta/15 text-violeta-ink"
          aria-hidden
        >
          {RECIBO}
        </span>
      </span>
    );
  }

  const label = pagado ? lblPago : lblFactura;
  return (
    <span
      className={cn(
        "inline-flex h-[18px] w-[18px] items-center justify-center rounded-full border align-middle text-2xs",
        pagado
          ? "border-verde/45 bg-verde/15 font-extrabold text-verde-ink"
          : "border-violeta/45 bg-violeta/15 text-violeta-ink",
        className,
      )}
      title={label}
      aria-label={label}
    >
      {pagado ? "$" : RECIBO}
    </span>
  );
}
