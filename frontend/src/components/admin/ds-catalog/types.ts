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
 * exige que TODO archivo de `design-system/ui` + `design-system/kit` aparezca en
 * algún `files` → un componente sin vitrina falla CI (no se olvida en silencio).
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
