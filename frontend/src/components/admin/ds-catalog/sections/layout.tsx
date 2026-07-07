/**
 * Sección Layout & Estructura — composites de armado de página del back-office:
 * encabezado + contenido reusable para paneles (Section) y tarjetas de métrica
 * (StatCard). Distinta de "Contenedores" (primitivos de UI como Card/Table) —
 * acá viven las piezas que ensamblan una página admin completa.
 */
import { User, DollarSign } from "lucide-react";

import { type CatalogSection } from "../types";
import { Caption, Row, Stack } from "../catalog-kit";
import { Section } from "@/design-system/composites/Section";
import { StatCard } from "@/design-system/composites/StatCard";

export const layoutSection: CatalogSection = {
  id: "layout",
  title: "Layout & Estructura",
  hint: "Section + StatCard: los composites que arman una página admin (reemplazan los wrappers locales que había repetidos por el repo).",
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
    {
      name: "StatCard",
      files: ["design-system/composites/StatCard.tsx"],
      blurb:
        "Label + valor grande + meta opcional. size=lg (default, dashboards) | md (tiles compactos en dialogs). tone=default|warn|destructive. icon opcional (ComponentType, no nodo).",
      render: () => (
        <Stack>
          <div className="space-y-1.5">
            <Caption>size=&quot;lg&quot; (default) — con y sin icon/tone</Caption>
            <Row>
              <StatCard label="Facturado 2026" value="$1.240.000" meta="pedido R-1039" />
              <StatCard icon={DollarSign} label="En juego" value="$84.000" meta="Pipeline" />
              <StatCard label="Huérfanos" value={3} tone="warn" />
            </Row>
          </div>
          <div className="space-y-1.5">
            <Caption>size=&quot;md&quot; — tiles compactos (dialogs)</Caption>
            <Row>
              <StatCard label="Eventos" value={12} size="md" />
              <StatCard label="Visibles" value={48} size="md" />
              <StatCard label="Vencido" value="12 jun 2026" tone="destructive" size="md" />
            </Row>
          </div>
        </Stack>
      ),
    },
  ],
};
