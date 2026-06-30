// governance.config.mjs — config por-repo del motor de gobernanza (portable).
//
// El MOTOR (scripts/check-docs.mjs + .claude/skills/*) es genérico y no debería tener rutas de este
// repo hardcodeadas. Acá vive lo repo-específico: dónde está la memoria, el front door y los skills.
// Para adoptar el sistema en otro repo: copiar `.claude/skills/` + `scripts/check-docs.mjs` y editar
// estas pocas líneas. Si este archivo no existe, `check-docs.mjs` cae a estos mismos defaults.

export default {
  // Memoria en dos sub-capas (digest auto-cargado + log on-demand), en paridad de headers.
  memoryDigest: "docs/MEMORIA.md",
  memoryLog: "docs/DECISIONES.md",

  // Front door que auto-carga el digest y lista los skills.
  claudeMd: "CLAUDE.md",
  // Patrón de import que CLAUDE.md tiene que seguir teniendo (auto-carga del digest).
  memoryImportPattern: "@docs/MEMORIA.md",

  // Dónde buscar links de gobernanza vivos (cross-refs no rotas).
  govDirs: ["docs/", ".claude/"],
  // Archivos sueltos de gobernanza en la raíz (además de los govDirs).
  govRootFiles: ["CLAUDE.md", "MANIFIESTO.md", "README.md"],

  // Dónde viven los skills (cada uno es un dir con su SKILL.md).
  skillsDir: ".claude/skills",
  // Umbral de staleness (días desde `last-reviewed:`) que dispara un warning (no error).
  skillStaleDays: 120,

  // Cobertura de la vitrina del Design System (anti-drift del catálogo).
  // Todo .tsx en `componentDirs` debe aparecer (por su path relativo a `srcRoot`)
  // en algún `Specimen.files` del catálogo → un componente sin vitrina falla CI.
  // Espeja la paridad skills↔registro: el manifiesto del catálogo es el registro.
  dsCatalog: {
    catalogDir: "frontend/src/components/admin/ds-catalog",
    srcRoot: "frontend/src",
    componentDirs: ["frontend/src/design-system/ui", "frontend/src/design-system/composites"],
    // Exenciones: componentes que NO van a la vitrina. Cada uno con comentario
    // ⏰ del porqué (mismo criterio de coexistencia temporal del resto del repo).
    exempt: [],
  },
};
