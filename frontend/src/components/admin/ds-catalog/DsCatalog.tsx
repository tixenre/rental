/**
 * DsCatalog — la vitrina del Design System de Rambla (la fuente de verdad, visible).
 *
 * Manifest-driven: mapea `CATALOG_BY_LAYER` (manifest.ts). Muestra TODO lo que el DS
 * cubre, agrupado por capa funcional —fundamentos, primitivos, composites, secciones,
 * páginas, flujos— para REUSAR (no recrear) y ver de un vistazo qué hay y qué falta.
 * Read-only por ahora; es la puerta de entrada al futuro editor de temas (los tokens de
 * color de acá son los que ese editor va a poder cambiar). Se renderiza como solapa
 * dentro de "Assets y diseño".
 *
 * Anti-drift: el guardrail de check-docs.mjs exige que todo archivo de
 * design-system/{ui,composites} esté en algún Specimen.files → no se desincroniza en silencio.
 */
import { Sparkles } from "lucide-react";

import { CATALOG, CATALOG_BY_LAYER } from "./manifest";
import { LayerHeading, SectionBlock, TocNav } from "./catalog-kit";

export function DsCatalog() {
  const total = CATALOG.reduce((n, s) => n + s.specimens.length, 0);
  return (
    <div className="space-y-8">
      <p className="text-sm text-muted-foreground">
        {CATALOG_BY_LAYER.length} capas · {CATALOG.length} secciones · {total} piezas. La librería
        viva — ordenada de la materia prima (tokens) al recorrido completo (flujos).
      </p>

      <TocNav groups={CATALOG_BY_LAYER} />

      <div className="space-y-12">
        {CATALOG_BY_LAYER.map((group) => (
          <div key={group.layer.id} className="space-y-8">
            <LayerHeading layer={group.layer} />
            {group.sections.map((section) => (
              <SectionBlock key={section.id} section={section} />
            ))}
          </div>
        ))}
      </div>

      <p className="flex items-center gap-2 border-t border-hairline pt-4 text-xs text-muted-foreground">
        <Sparkles className="h-3.5 w-3.5 shrink-0" />
        Próximo: editor de temas — cambiar estos tokens desde acá, con preview en vivo.
      </p>
    </div>
  );
}
