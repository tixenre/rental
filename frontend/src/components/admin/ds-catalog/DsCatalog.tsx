/**
 * DsCatalog — la vitrina del Design System de Rambla (la fuente de verdad, visible).
 *
 * Manifest-driven: mapea `CATALOG` (manifest.ts). Muestra TODO lo que el DS cubre
 * —tokens, primitivos, kit, presentacionales, páginas— para REUSAR (no recrear) y
 * para ver de un vistazo qué hay y qué falta. Read-only por ahora; es la puerta de
 * entrada al futuro editor de temas (los tokens de color de acá son los que ese
 * editor va a poder cambiar). Se renderiza como solapa dentro de "Assets y diseño".
 *
 * Anti-drift: el guardrail de check-docs.mjs exige que todo archivo de
 * design-system/{ui,kit} esté en algún Specimen.files → no se desincroniza en silencio.
 */
import { Sparkles } from "lucide-react";

import { CATALOG } from "./manifest";
import { SectionBlock, TocNav } from "./catalog-kit";

export function DsCatalog() {
  const total = CATALOG.reduce((n, s) => n + s.specimens.length, 0);
  return (
    <div className="space-y-8">
      <p className="text-sm text-muted-foreground">
        {CATALOG.length} secciones · {total} piezas. La librería viva — lo que hay que reusar.
      </p>

      <TocNav sections={CATALOG} />

      <div className="space-y-12">
        {CATALOG.map((section) => (
          <SectionBlock key={section.id} section={section} />
        ))}
      </div>

      <p className="flex items-center gap-2 border-t border-hairline pt-4 text-xs text-muted-foreground">
        <Sparkles className="h-3.5 w-3.5 shrink-0" />
        Próximo: editor de temas — cambiar estos tokens desde acá, con preview en vivo.
      </p>
    </div>
  );
}
