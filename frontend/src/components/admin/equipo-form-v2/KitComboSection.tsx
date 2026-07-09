/**
 * KitComboSection — editor de componentes del kit/combo (solo EDIT).
 *
 * Extraído verbatim de `EquipoFormDialogV2.tsx` (split de god-module, Frente E
 * del skill `mantenimiento`, F2b #1263). Cero cambio de comportamiento — el
 * gate `mostrarSeccionesEdit` (isEdit && initial) queda en el padre, que
 * decide si monta esta sección.
 */
import { KitEditor } from "./KitEditor";
import { ComboEditor } from "./ComboEditor";
import { CollapsibleSection } from "./form-helpers";

export function KitComboSection({ esCombo, equipoId }: { esCombo: boolean; equipoId: number }) {
  return (
    <CollapsibleSection title={esCombo ? "Componentes del combo" : "Kit (componentes incluidos)"}>
      {esCombo ? <ComboEditor equipoId={equipoId} /> : <KitEditor equipoId={equipoId} />}
    </CollapsibleSection>
  );
}
