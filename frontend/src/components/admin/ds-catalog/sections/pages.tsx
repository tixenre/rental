/**
 * Sección Páginas & Patterns — cierra el loop "componente → pantalla real".
 *
 * No son mini-renders a mano (eso se desincroniza): cada arquetipo linkea a la
 * pantalla VERDADERA (siempre actual) + cuántas instancias hay. Abajo, los bloques
 * compuestos que viven entre primitivo y página (donde más se reinventa).
 *
 * Pendiente (siguiente paso): miniatura por arquetipo generada con el harness
 * Playwright de `auditoria-profunda` (recorre 320→1920) — thumbnail sin mantener a mano.
 */
import { ArrowUpRight, Inbox } from "lucide-react";

import { type CatalogSection } from "../types";
import { Caption } from "../catalog-kit";
import { Button } from "@/design-system/ui/button";
import { AdminPage } from "@/components/admin/AdminPage";
import { EmptyState } from "@/components/rental/EmptyState";

type Archetype = {
  name: string;
  count: number;
  desc: string;
  /** Patrón de ruta (puede llevar $param). */
  example: string;
  /** Ruta navegable sin params, si existe (abre la pantalla real). */
  href?: string;
};

// Los 15 arquetipos de pantalla del relevamiento (excluye "redirect", que no es layout).
const ARCHETYPES: Archetype[] = [
  {
    name: "list-table",
    count: 14,
    desc: "Tabla/listado con filtros, búsqueda y acciones por fila. El arquetipo dominante del back-office (ABMs y bandejas).",
    example: "/admin/pedidos",
    href: "/admin/pedidos",
  },
  {
    name: "dashboard",
    count: 6,
    desc: "Overview con KPIs/tarjetas/atajos y métricas agregadas; no una sola tabla.",
    example: "/admin",
    href: "/admin",
  },
  {
    name: "legal-prose",
    count: 6,
    desc: "Documento de texto largo en columna estrecha: legales, FAQ con acordeones, glosario.",
    example: "/preguntas-frecuentes",
    href: "/preguntas-frecuentes",
  },
  {
    name: "marketing-landing",
    count: 4,
    desc: "Página de marketing ancho completo: hero, secciones narrativas, CTA. Hub y cada área pública.",
    example: "/",
    href: "/",
  },
  {
    name: "form-detail",
    count: 4,
    desc: "Editor de una entidad existente: campos pre-cargados, secciones, guardar.",
    example: "/admin/equipos/$id/editar",
    href: "/admin/equipos/nuevo",
  },
  {
    name: "settings",
    count: 4,
    desc: "Configuración: secciones colapsables o tabs que agrupan controles de sistema.",
    example: "/admin/settings",
    href: "/admin/settings",
  },
  {
    name: "auth",
    count: 3,
    desc: "Pantalla de autenticación centrada (login).",
    example: "/admin/login",
    href: "/admin/login",
  },
  {
    name: "form-wizard",
    count: 3,
    desc: "Formulario largo multi-sección para crear una entidad compleja (alta de pedido / cliente).",
    example: "/admin/pedidos/nuevo",
    href: "/admin/pedidos/nuevo",
  },
  {
    name: "report",
    count: 2,
    desc: "Reporte financiero: tablas de cálculo, totales, cascada P&L, cierres. Más denso en números.",
    example: "/admin/contabilidad/reporte",
    href: "/admin/contabilidad/reporte",
  },
  {
    name: "public-grid",
    count: 2,
    desc: "Grilla de catálogo público con filtros/búsqueda y cards de equipo (+ variante mobile).",
    example: "/rental",
    href: "/rental",
  },
  {
    name: "detail",
    count: 2,
    desc: "Detalle de una entidad pública (ficha de equipo, carrito compartido) + acción primaria.",
    example: "/equipo/$slug",
  },
  {
    name: "list-cards",
    count: 1,
    desc: "Lista de entidades como cards expandibles con búsqueda — el portal de pedidos del cliente.",
    example: "/cliente/portal",
  },
  {
    name: "detail-editor",
    count: 1,
    desc: "Editor pesado de un pedido: ítems, estado, plata, documentos y timeline en una pantalla.",
    example: "/admin/pedidos/$id",
  },
  {
    name: "ds-showcase",
    count: 1,
    desc: "QA visual del DS — esta misma vitrina (antes /kit-preview, ahora consolidada acá).",
    example: "/admin/diseno",
  },
];

function ArchetypeCard({ a }: { a: Archetype }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border hairline bg-surface p-4">
      <div className="flex items-center justify-between gap-2">
        <h4 className="font-display text-sm text-ink">{a.name}</h4>
        <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-2xs text-muted-foreground">
          ×{a.count}
        </span>
      </div>
      <p className="flex-1 text-xs text-muted-foreground">{a.desc}</p>
      <div className="flex items-center justify-between gap-2">
        <code className="t-mono text-2xs text-ink/70">{a.example}</code>
        {a.href && (
          <a
            href={a.href}
            target="_blank"
            rel="noreferrer"
            className="inline-flex shrink-0 items-center gap-0.5 text-2xs font-medium text-muted-foreground transition-colors hover:text-ink"
          >
            ver <ArrowUpRight className="h-3 w-3" />
          </a>
        )}
      </div>
    </div>
  );
}

export const pagesSection: CatalogSection = {
  id: "paginas",
  title: "Páginas & Patterns",
  hint: "El mapa de pantallas: 15 arquetipos, cuántos hay de cada uno, link a la pantalla real. Y los bloques compuestos que se montan entre primitivo y página.",
  specimens: [
    {
      name: "Arquetipos de página",
      files: [],
      blurb:
        "Cada tipo de pantalla que existe en la app, con su ejemplo canónico. El link abre la pantalla verdadera (no un mock que miente).",
      render: () => (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {ARCHETYPES.map((a) => (
            <ArchetypeCard key={a.name} a={a} />
          ))}
        </div>
      ),
    },
    {
      name: "AdminPage",
      files: ["components/admin/AdminPage.tsx"],
      blurb:
        "El chrome único de página del back-office: eyebrow + título + descripción + acciones + back-link. Absorbe el header que estaba copy-pasteado en ~26 rutas.",
      render: () => (
        <div className="overflow-hidden rounded-lg border hairline bg-background">
          <AdminPage
            title="Título de la página"
            eyebrow="Sección"
            description="La bajada opcional que explica la pantalla."
            actions={
              <Button variant="primary" size="sm">
                Acción
              </Button>
            }
          >
            <div className="rounded-md border hairline bg-surface p-4 text-sm text-muted-foreground">
              …contenido de la página…
            </div>
          </AdminPage>
        </div>
      ),
    },
    {
      name: "EmptyState con CTA",
      files: ["components/rental/EmptyState.tsx"],
      blurb:
        "El patrón de vacío con acción: no dejar al usuario en un callejón — siempre un próximo paso.",
      render: () => (
        <div className="rounded-lg border hairline">
          <EmptyState
            icon={<Inbox className="h-6 w-6" />}
            title="Todavía no hay pedidos"
            sub="Cuando entre una solicitud, la vas a ver acá."
          >
            <Button variant="amber" size="sm">
              Crear pedido
            </Button>
          </EmptyState>
        </div>
      ),
    },
    {
      name: "Bloques compuestos",
      files: [],
      blurb:
        "Otros bloques entre primitivo y página viven en el código y se reusan: TopBar por área (components/rental/TopBar.tsx), las cards de pedido del portal, QueryState montado sobre una query real. Se documentan acá como referencia.",
      render: () => (
        <div className="space-y-1.5 text-sm text-muted-foreground">
          <Caption>en el código — reusar, no recrear</Caption>
          <ul className="ml-4 list-disc space-y-1">
            <li>
              <code className="t-mono text-xs text-ink">TopBar</code> — shell único de navegación
              por área (rental/estudio/workshops/cliente), color de marca y logo themeable.
            </li>
            <li>
              <code className="t-mono text-xs text-ink">QueryState</code> montado sobre un{" "}
              <code className="t-mono text-xs text-ink">useQuery</code> real (ver sección Estados).
            </li>
          </ul>
        </div>
      ),
    },
  ],
};
