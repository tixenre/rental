/**
 * ContenidoIncluidoSection — qué viene en la caja (B1 #635) + "Imprimir
 * contenido" (packing list). Solo EDIT.
 *
 * Extraído verbatim de `EquipoFormDialogV2.tsx` (split de god-module, Frente E
 * del skill `mantenimiento`, F2c #1263). Cero cambio de comportamiento.
 */
import { Printer } from "lucide-react";
import { Button } from "@/design-system/ui/button";
import { CollapsibleSection } from "./form-helpers";
import { ContenidoIncluidoEditor } from "./ContenidoIncluidoEditor";
import { buildContenidoIncluidoPrintHtml } from "./contenido-incluido-print";
import type { ContenidoIncluidoItem } from "@/data/equipment";
import type { Equipo } from "@/lib/admin/api";

export function ContenidoIncluidoSection({
  equipo,
  items,
  onChange,
}: {
  equipo: Equipo;
  items: ContenidoIncluidoItem[];
  onChange: (items: ContenidoIncluidoItem[]) => void;
}) {
  return (
    <CollapsibleSection title="Contenido de la caja" defaultOpen={items.length > 0}>
      <div className="flex items-start justify-between mb-2 gap-2">
        <p className="text-xs text-muted-foreground">
          Qué viene en la caja (reflector, fuente, cables, estuche). Solo informativo — no afecta
          reservas ni stock.
        </p>
        {items.length > 0 && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="shrink-0"
            onClick={() => {
              const html = buildContenidoIncluidoPrintHtml(equipo, items);
              const w = window.open("", "_blank", "width=700,height=600");
              if (w) {
                w.document.write(html);
                w.document.close();
              }
            }}
          >
            <Printer className="h-3 w-3 mr-1" />
            Imprimir contenido
          </Button>
        )}
      </div>
      <ContenidoIncluidoEditor equipoId={equipo.id} items={items} onChange={onChange} />
    </CollapsibleSection>
  );
}
