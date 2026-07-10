/**
 * KitComboSection — editor de componentes del kit/combo (solo EDIT).
 *
 * Extraído verbatim de `EquipoFormDialog.tsx` (split de god-module, Frente E
 * del skill `mantenimiento`, F2b #1263). Cero cambio de comportamiento — el
 * gate `mostrarSeccionesEdit` (isEdit && initial) queda en el padre, que
 * decide si monta esta sección.
 */
import { lazy, memo, Suspense } from "react";
import { Spinner } from "@/design-system/ui/spinner";
import { CollapsibleSection } from "./form-helpers";

// Lazy: dnd-kit + KitComponentEditor no tienen por qué viajar al bundle de
// CREATE, donde esta sección es inalcanzable (mostrarSeccionesEdit = isEdit
// && initial, en el padre). `.then()` adapta el export nombrado al shape
// { default } que pide React.lazy, sin tocar KitEditor.tsx/ComboEditor.tsx
// (ComboEditor también lo importa, nombrado, ComboBuilderDialog.tsx).
const KitEditor = lazy(() => import("./KitEditor").then((m) => ({ default: m.KitEditor })));
const ComboEditor = lazy(() => import("./ComboEditor").then((m) => ({ default: m.ComboEditor })));

// memo: sin este boundary, cualquier re-render del padre (ej. tipear en otro
// campo del form) re-renderiza igual a KitEditor/ComboEditor y su DndContext.
function KitComboSectionImpl({ esCombo, equipoId }: { esCombo: boolean; equipoId: number }) {
  return (
    <CollapsibleSection title={esCombo ? "Componentes del combo" : "Kit (componentes incluidos)"}>
      <Suspense fallback={<Spinner size="sm" className="mx-auto" />}>
        {esCombo ? <ComboEditor equipoId={equipoId} /> : <KitEditor equipoId={equipoId} />}
      </Suspense>
    </CollapsibleSection>
  );
}

export const KitComboSection = memo(KitComboSectionImpl);
