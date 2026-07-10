/**
 * FichaTecnicaSection — categoría de specs + editor de specs estructuradas.
 *
 * Extraído verbatim de `EquipoFormDialog.tsx` (split de god-module, Frente E
 * del skill `mantenimiento`, F2b #1263). Cero cambio de comportamiento — todo
 * lo que necesita ya vive en `draft` (issue #1263 F1); `specCatOptions` es lo
 * único externo (referencia resuelta por el padre desde `specCatsQ`).
 */
import { memo } from "react";
import { CollapsibleSection } from "./form-helpers";
import { Field } from "./form-helpers";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/design-system/ui/select";
import { SpecsDiffEditor } from "./SpecsDiffEditor";
import type { EquipoFormDraft } from "./useEquipoFormDraft";

// memo: `draft` viaja entero y ahora está memoizado (useEquipoFormDraft) —
// sin este boundary, cualquier re-render del padre (ej. tipear en otro campo)
// re-renderiza igual a SpecsDiffEditor de abajo.
function FichaTecnicaSectionImpl({
  draft,
  specCatOptions,
}: {
  draft: EquipoFormDraft;
  specCatOptions: { id: number; nombre: string }[];
}) {
  const {
    categoriaSpecs,
    setCategoriaSpecs,
    specs,
    setSpecs,
    specsPropuestos,
    templateItems,
    aceptarPropuesto,
    descartarPropuesto,
  } = draft;

  return (
    <CollapsibleSection
      title="Ficha técnica"
      defaultOpen={specsPropuestos.length > 0 || specs.length > 0 || !!categoriaSpecs}
    >
      <div className="space-y-3">
        <Field label="Categoría de specs">
          <Select
            value={categoriaSpecs || "__none__"}
            onValueChange={(v) => setCategoriaSpecs(v === "__none__" ? "" : v)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Sin categoría de specs" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">Sin categoría de specs</SelectItem>
              {specCatOptions.map((c) => (
                <SelectItem key={c.id} value={c.nombre}>
                  {c.nombre}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Define qué specs técnicas aplican y el nombre público. Al elegirla aparecen los specs
            abajo. Independiente del catálogo.
          </p>
        </Field>

        <SpecsDiffEditor
          specs={specs}
          propuestos={specsPropuestos}
          templateItems={templateItems}
          onChange={setSpecs}
          onAceptarPropuesto={aceptarPropuesto}
          onDescartarPropuesto={descartarPropuesto}
        />
      </div>
    </CollapsibleSection>
  );
}

export const FichaTecnicaSection = memo(FichaTecnicaSectionImpl);
