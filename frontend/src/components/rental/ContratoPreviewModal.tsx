/**
 * ContratoPreviewModal — deja leer el contrato del pedido EN CURSO antes de
 * confirmar, sin salir del checkout (mismo criterio que FacturacionModal/
 * TerminosModal). El HTML lo arma el backend con el mismo generador que el
 * contrato real de un pedido ya creado (`_contrato_html`), pero marcado como
 * SIMULACIÓN — no persiste nada; el documento válido queda en el portal y se
 * manda por mail recién al confirmar. Sienta base para la firma digital de
 * #1098 Fase 5 (leer antes de firmar).
 */
import { useEffect, useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/design-system/ui/dialog";
import { Spinner } from "@/design-system/ui/spinner";
import { obtenerContratoPreviewHtml } from "@/lib/checkout";

export function ContratoPreviewModal({
  open,
  onOpenChange,
  sessionId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  sessionId: string;
}) {
  const [html, setHtml] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setCargando(true);
    setError(null);
    obtenerContratoPreviewHtml(sessionId)
      .then((h) => {
        if (alive) setHtml(h);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : "No pudimos cargar el contrato.");
      })
      .finally(() => {
        if (alive) setCargando(false);
      });
    return () => {
      alive = false;
    };
  }, [open, sessionId]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[85vh] w-full flex-col overflow-hidden p-0 sm:max-w-3xl">
        <DialogHeader className="border-b hairline px-6 py-4">
          <DialogTitle>Tu contrato — vista previa</DialogTitle>
          <DialogDescription>
            Simulación del pedido en curso, para que sepas qué vas a firmar. No es un documento
            válido: el definitivo queda en tu portal y te lo mandamos por mail al confirmar.
          </DialogDescription>
        </DialogHeader>
        <div className="flex-1 overflow-hidden bg-white">
          {cargando && (
            <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
              <Spinner size="sm" />
              Armando el preview…
            </div>
          )}
          {!cargando && error && (
            <div className="flex h-full items-center justify-center px-6 text-center text-sm text-destructive">
              {error}
            </div>
          )}
          {!cargando && !error && html && (
            <iframe
              srcDoc={html}
              title="Contrato (vista previa)"
              className="h-full w-full border-0"
              sandbox=""
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
