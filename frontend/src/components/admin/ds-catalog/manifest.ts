/**
 * manifest — el registro ordenado de la librería del DS.
 *
 * Fuente única de QUÉ muestra la vitrina y de CÓMO se ordena (por capa funcional).
 * Agregar un componente al DS = agregar su Specimen a la sección que corresponda
 * (y su archivo a `Specimen.files`, que el guardrail de check-docs.mjs verifica).
 *
 * El orden visual NO sale del orden de declaración: sale de `LAYERS` (las capas,
 * de materia prima → recorrido completo) + `SECTION_LAYER` (la capa de cada
 * sección). La clasificación es por FUNCIÓN (tamaño de composición), no por
 * dominio:
 *   fundamentos → tokens (la materia prima)
 *   primitivos  → átomos sin dominio (botón, input, pill, modal)
 *   composites  → combinaciones genéricas reusables (estado vacío, carga/error)
 *   secciones   → organismos de dominio (las piezas de equipos)
 *   paginas     → arquetipos de página completos
 *   flujos      → recorridos con lógica viva (carrito, fechas)
 */
import type { CatalogLayer, CatalogSection, LayerGroup, LayerMeta } from "./types";

import { foundationsSection } from "./sections/foundations";
import { actionsSection } from "./sections/actions";
import { badgesSection } from "./sections/badges";
import { formsSection } from "./sections/forms";
import { moneySection } from "./sections/money";
import { overlaysSection } from "./sections/overlays";
import { navigationSection } from "./sections/navigation";
import { containersSection } from "./sections/containers";
import { statesSection } from "./sections/states";
import { catalogSharedSection } from "./sections/catalog-shared";
import { catalogoOrganismosSection } from "./sections/catalogo-organismos";
import { clienteOrganismosSection } from "./sections/cliente-organismos";
import { feedbackSection } from "./sections/feedback";
import { flujosSection } from "./sections/flujos";
import { pagesSection } from "./sections/pages";

/** Las capas, en orden de render (materia prima → recorrido completo). */
export const LAYERS: LayerMeta[] = [
  {
    id: "fundamentos",
    label: "Fundamentos",
    blurb:
      "Los tokens: color, tipografía, radios, sombras, motion. La materia prima de todo lo demás.",
  },
  {
    id: "primitivos",
    label: "Primitivos",
    blurb:
      "Las piezas atómicas, sin dominio — botón, input, pill, modal. Los ladrillos: se reusan, no se recrean.",
  },
  {
    id: "composites",
    label: "Composites",
    blurb: "Combinaciones genéricas y reusables: estado vacío, manejo de carga / error.",
  },
  {
    id: "secciones",
    label: "Secciones",
    blurb:
      "Organismos del dominio: las piezas ensambladas de cada área — el cluster compartido de equipos (precio, stepper, favorito), el catálogo público (card, lista, buscador, carrito) y el portal del cliente (pedido, identidad, listas). Viven en components/ y routes/, no en la librería pura, pero son canónicos.",
  },
  {
    id: "paginas",
    label: "Páginas",
    blurb: "Arquetipos de página completos, con links vivos a la app.",
  },
  {
    id: "flujos",
    label: "Flujos",
    blurb: "Recorridos con lógica viva: carrito, selección de fechas, guardar lista.",
  },
];

/**
 * La capa de cada sección (única fuente). El id es el `CatalogSection.id`.
 * `check-docs.mjs` verifica que toda sección del manifiesto tenga su capa acá.
 */
const SECTION_LAYER: Record<string, CatalogLayer> = {
  fundamentos: "fundamentos",
  acciones: "primitivos",
  badges: "primitivos",
  formularios: "primitivos",
  plata: "primitivos",
  overlays: "primitivos",
  navegacion: "primitivos",
  contenedores: "primitivos",
  notificaciones: "primitivos",
  estados: "composites",
  "catalogo-shared": "secciones",
  "catalogo-organismos": "secciones",
  "cliente-organismos": "secciones",
  paginas: "paginas",
  flujos: "flujos",
};

/** Todas las secciones (el orden acá no importa — se reordena por capa). */
const SECTIONS: CatalogSection[] = [
  foundationsSection,
  actionsSection,
  badgesSection,
  formsSection,
  moneySection,
  overlaysSection,
  navigationSection,
  containersSection,
  statesSection,
  catalogSharedSection,
  catalogoOrganismosSection,
  clienteOrganismosSection,
  feedbackSection,
  flujosSection,
  pagesSection,
];

/** Agrupado por capa — lo que renderiza la página (con encabezados de capa). */
export const CATALOG_BY_LAYER: LayerGroup[] = LAYERS.map((layer) => ({
  layer,
  sections: SECTIONS.filter((s) => SECTION_LAYER[s.id] === layer.id),
})).filter((g) => g.sections.length > 0);

/** Flat, en orden de capa — consumido por el conteo y el guardrail anti-drift. */
export const CATALOG: CatalogSection[] = CATALOG_BY_LAYER.flatMap((g) => g.sections);

// Red de seguridad: toda sección DEBE tener capa en SECTION_LAYER, si no la vista
// por capas la dejaría afuera en silencio. Fallar fuerte al cargar la vitrina.
const sinCapa = SECTIONS.filter((s) => !SECTION_LAYER[s.id]).map((s) => s.id);
if (sinCapa.length) {
  throw new Error(
    `ds-catalog/manifest: sección(es) sin capa en SECTION_LAYER: ${sinCapa.join(", ")}. ` +
      `Asignales una capa (si no, el orden por capa las omite).`,
  );
}
