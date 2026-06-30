import { type ReactNode } from "react";

/**
 * Contrato del catálogo del Design System (manifest-driven).
 *
 * La librería NO es un JSX gigante a mano: es un manifiesto (`manifest.ts`) de
 * secciones, cada una con sus `Specimen`. La página (`DsCatalog.tsx`) mapea el
 * manifiesto. Agregar un componente al DS = agregar su `Specimen` a su sección.
 *
 * `Specimen.files` es la clave anti-drift: lista los archivos fuente que el
 * specimen cubre (relativos a `frontend/src`). El guardrail de `check-docs.mjs`
 * exige que TODO archivo de `design-system/ui` + `design-system/composites`
 * aparezca en algún `files` → un componente sin vitrina falla CI (no se olvida
 * en silencio).
 */

/** Un specimen = la demo en vivo de UN componente (o token-group) del DS. */
export type Specimen = {
  /** Nombre visible. Ej: "Button". */
  name: string;
  /**
   * Archivo(s) fuente que cubre, relativos a `frontend/src`.
   * Ej: ["design-system/ui/button.tsx"]. Vacío para tiles de token/fundamento
   * que no mapean a un componente (colores, tipografía…).
   */
  files: string[];
  /** Una línea: qué es / cuándo usarlo. */
  blurb?: string;
  /** El demo en vivo. */
  render: () => ReactNode;
};

/** Una sección del catálogo agrupa specimens afines. */
export type CatalogSection = {
  /** id estable — ancla de navegación (`#id`). */
  id: string;
  /** Título visible. */
  title: string;
  /** Bajada opcional. */
  hint?: string;
  specimens: Specimen[];
};

/**
 * Las capas funcionales de la librería, en orden ascendente de composición:
 * de la materia prima (tokens) al recorrido completo (flujos). La clasificación
 * es por FUNCIÓN (tamaño de composición), no por dominio. Ver `manifest.ts`.
 */
export type CatalogLayer =
  | "fundamentos"
  | "primitivos"
  | "composites"
  | "secciones"
  | "paginas"
  | "flujos";

/** Encabezado visible de una capa en la vitrina. */
export type LayerMeta = {
  id: CatalogLayer;
  label: string;
  /** Una línea en lenguaje claro: qué es esta capa. */
  blurb: string;
};

/** Una capa con las secciones que le tocan — la unidad de render agrupado. */
export type LayerGroup = {
  layer: LayerMeta;
  sections: CatalogSection[];
};
