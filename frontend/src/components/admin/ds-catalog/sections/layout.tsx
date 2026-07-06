/**
 * Sección Layout & Estructura — composites de armado de página del back-office:
 * encabezado + contenido reusable para paneles (Section). Distinta de
 * "Contenedores" (primitivos de UI como Card/Table) — acá viven las piezas que
 * ensamblan una página admin completa.
 */
import { User } from "lucide-react";

import { type CatalogSection } from "../types";
import { Caption, Stack } from "../catalog-kit";
import { Section } from "@/design-system/composites/Section";

export const layoutSection: CatalogSection = {
  id: "layout",
  title: "Layout & Estructura",
  hint: "Section: encabezado + contenido único para paneles admin (reemplaza los 6 wrappers locales que había en el repo).",
  specimens: [
    {
      name: "Section",
      files: ["design-system/composites/Section.tsx"],
      blurb:
        "variant=card (default, con borde+fondo) o plain (sin chrome). tone=elevated separa el header en una tira con borde inferior. icon/actions opcionales.",
      render: () => (
        <Stack>
          <div className="space-y-1.5">
            <Caption>variant=&quot;card&quot; tone=&quot;default&quot;</Caption>
            <Section title="Cliente" subtitle="Datos de contacto">
              <p className="text-sm text-muted-foreground">Contenido del panel.</p>
            </Section>
          </div>
          <div className="space-y-1.5">
            <Caption>variant=&quot;card&quot; tone=&quot;elevated&quot; + icon</Caption>
            <Section variant="card" tone="elevated" icon={User} title="Cliente">
              <p className="text-sm text-muted-foreground">Contenido del panel.</p>
            </Section>
          </div>
          <div className="space-y-1.5">
            <Caption>variant=&quot;plain&quot; (sin chrome, para páginas ya envueltas)</Caption>
            <Section variant="plain" title="Assets canónicos" subtitle="rambla.house">
              <p className="text-sm text-muted-foreground">Contenido del panel.</p>
            </Section>
          </div>
        </Stack>
      ),
    },
  ],
};
