/**
 * EquipoThumb — miniatura cuadrada de la foto de un equipo, con fallback al
 * ícono de carrito cuando no hay foto (o falla la carga). Fuente única para los
 * dos lugares del editor de pedido que muestran equipos: la lista de ítems del
 * pedido y el buscador (`EquipoSearchSheet`). Evita repetir el patrón
 * img+onError+fallback "parecido pero distinto" en cada lugar.
 */

import { useState } from "react";
import { ShoppingCart } from "lucide-react";
import { cn } from "@/lib/utils";

export function EquipoThumb({
  src,
  alt,
  className,
}: {
  src?: string | null;
  alt?: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const showImg = !!src && !failed;

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center overflow-hidden rounded-md border hairline bg-muted/40 text-muted-foreground shrink-0",
        className,
      )}
    >
      {showImg ? (
        <img
          src={src!}
          alt={alt ?? ""}
          loading="lazy"
          onError={() => setFailed(true)}
          className="h-full w-full object-contain p-0.5"
        />
      ) : (
        <ShoppingCart className="h-4 w-4" />
      )}
    </span>
  );
}
