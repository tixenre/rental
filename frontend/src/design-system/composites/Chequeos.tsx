import { Check, X, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Chequeo {
  check: string;
  ok: boolean;
  bloqueante: boolean;
  mensaje: string;
}

/**
 * Lista de chequeos `{check, ok, bloqueante, mensaje}` — mismo shape que devuelve
 * `_chequeos_previos`/`previsualizar_factura` y `diagnosticar_emisor` en el backend.
 * Tres estados: ok = check verde, falla bloqueante = X roja, falla no-bloqueante = triángulo ámbar.
 * Extraído de `pedidos.$id.lazy.tsx` (preview de factura) — reusado también por el
 * diagnóstico de configuración del emisor, para no duplicar esta lógica de 3 estados.
 */
export function Chequeos({ items, className }: { items: Chequeo[]; className?: string }) {
  return (
    <div className={cn("space-y-1.5", className)}>
      {items.map((c) => (
        <div key={c.check} className="flex items-start gap-2 text-xs">
          {c.ok ? (
            <Check className="h-3.5 w-3.5 shrink-0 mt-0.5 text-verde-ink" />
          ) : c.bloqueante ? (
            <X className="h-3.5 w-3.5 shrink-0 mt-0.5 text-destructive" />
          ) : (
            // eslint-disable-next-line no-restricted-syntax -- amber: paleta categórica de advertencia (Tier 3), ya usada en esta pantalla
            <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5 text-amber-600" />
          )}
          <span
            className={cn(!c.ok && c.bloqueante ? "text-destructive" : "text-muted-foreground")}
          >
            {c.mensaje}
          </span>
        </div>
      ))}
    </div>
  );
}
