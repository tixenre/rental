/**
 * manifest — el registro ordenado de la librería del DS.
 *
 * Fuente única de QUÉ muestra la vitrina. Agregar un componente al DS = agregar
 * su Specimen a la sección que corresponda (y su archivo a `Specimen.files`, que
 * el guardrail de check-docs.mjs verifica). El orden de este array es el orden
 * en que se renderiza la página y el índice de salto (TocNav).
 */
import type { CatalogSection } from "./types";

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
import { feedbackSection } from "./sections/feedback";
import { pagesSection } from "./sections/pages";

export const CATALOG: CatalogSection[] = [
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
  feedbackSection,
  pagesSection,
];
