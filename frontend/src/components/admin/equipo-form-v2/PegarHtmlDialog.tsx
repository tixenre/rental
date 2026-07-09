/**
 * PegarHtmlDialog — "Pegar HTML" (#1051 Stream B): hermano JSON de "Subir
 * HTML" (mismo extractor, sin persistir archivo en R2).
 *
 * Extraído verbatim de `EquipoFormDialogV2.tsx` (split de god-module, Frente E
 * del skill `mantenimiento`, F2c #1263). Cero cambio de comportamiento.
 *
 * Historia: este modal vivía en la variante "dialog" de EquipoFormDialogV2,
 * que ningún caller usaba — el botón que abre el modal seteaba
 * `htmlPasteOpen` pero nada lo mostraba nunca. Bug real, confirmado y
 * arreglado en #1263 Fase 0 (el modal se movió a la variante que sí se
 * renderiza, antes de este split a componente propio).
 */
import { Spinner } from "@/design-system/ui/spinner";
import { Button } from "@/design-system/ui/button";
import { Textarea } from "@/design-system/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/design-system/ui/dialog";

export function PegarHtmlDialog({
  open,
  onOpenChange,
  text,
  onTextChange,
  pending,
  onCancel,
  onExtract,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  text: string;
  onTextChange: (v: string) => void;
  pending: boolean;
  onCancel: () => void;
  onExtract: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(v) => !pending && onOpenChange(v)}>
      <DialogContent className="w-full sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Pegar HTML del producto</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">
            Pegá el HTML completo de la página del producto (ej. copiado con Chrome MCP o
            Cmd+A/Cmd+C sobre "Ver código fuente"). Mismo extractor que "Subir HTML", pero acá no
            queda un archivo guardado.
          </p>
          <Textarea
            value={text}
            onChange={(e) => onTextChange(e.target.value)}
            placeholder="<html>…</html>"
            className="min-h-[240px] font-mono text-xs"
            disabled={pending}
          />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel} disabled={pending}>
            Cancelar
          </Button>
          <Button type="button" onClick={onExtract} disabled={pending}>
            {pending ? (
              <>
                <Spinner size="xs" className="mr-1" /> Extrayendo…
              </>
            ) : (
              "Extraer specs y fotos"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
