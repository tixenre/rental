/**
 * DsCatalog — la vitrina del Design System de Rambla (la fuente de verdad, visible).
 *
 * Manifest-driven: mapea `CATALOG_BY_LAYER` (manifest.ts). Muestra TODO lo que el DS
 * cubre, **una pestaña por capa** funcional —fundamentos, primitivos, composites, secciones,
 * páginas, flujos— para REUSAR (no recrear) y ver de un vistazo qué hay y qué falta.
 * Read-only por ahora; es la puerta de entrada al futuro editor de temas (los tokens de
 * color de acá son los que ese editor va a poder cambiar). Se renderiza como solapa
 * dentro de "Assets y diseño".
 *
 * Anti-drift: el guardrail de check-docs.mjs exige que todo archivo de
 * design-system/{ui,composites} esté en algún Specimen.files → no se desincroniza en silencio.
 */
import { Sparkles } from "lucide-react";

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/design-system/ui/tabs";
import { CATALOG, CATALOG_BY_LAYER } from "./manifest";
import { SectionBlock, SectionNav } from "./catalog-kit";

export function DsCatalog() {
  const total = CATALOG.reduce((n, s) => n + s.specimens.length, 0);
  const firstLayer = CATALOG_BY_LAYER[0]?.layer.id;
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        {CATALOG_BY_LAYER.length} capas · {CATALOG.length} secciones · {total} piezas. Una pestaña
        por capa — de la materia prima (tokens) al recorrido completo (flujos).
      </p>

      <Tabs defaultValue={firstLayer}>
        <TabsList className="h-auto flex-wrap justify-start">
          {CATALOG_BY_LAYER.map((group) => (
            <TabsTrigger key={group.layer.id} value={group.layer.id}>
              {group.layer.label}
            </TabsTrigger>
          ))}
        </TabsList>

        {CATALOG_BY_LAYER.map((group) => (
          <TabsContent key={group.layer.id} value={group.layer.id} className="space-y-6">
            <p className="max-w-2xl text-sm text-muted-foreground">{group.layer.blurb}</p>
            {group.sections.length > 1 && <SectionNav sections={group.sections} />}
            <div className="space-y-8">
              {group.sections.map((section) => (
                <SectionBlock key={section.id} section={section} />
              ))}
            </div>
          </TabsContent>
        ))}
      </Tabs>

      <p className="flex items-center gap-2 border-t border-hairline pt-4 text-xs text-muted-foreground">
        <Sparkles className="h-3.5 w-3.5 shrink-0" />
        Próximo: editor de temas — cambiar estos tokens desde acá, con preview en vivo.
      </p>
    </div>
  );
}
