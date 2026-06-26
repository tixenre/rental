// ── Áreas de Rambla — fuente única ─────────────────────────────────────────────
// Las 3 áreas públicas con su identidad de marca. La consumen el TopBar
// (SECTION_CONFIG), el menú de navegación (AreaMenu) y el hub. Cambiar el color,
// la ruta o el label de un área se hace acá una sola vez.
//
// - `label`: nombre con punto, font-display lowercase ("rental.")
// - `desc`:  bajada corta (menú de áreas)
// - `href`:   root del área
// - `bg`:     clase de fondo de marca (topbar)
// - `fg`:     color de texto legible sobre `bg` (logo/contenido sobre el color)
// - `accent`: color de marca como texto (wordmark/label en el SectionBanner)

export const AREAS = {
  rental: {
    label: "rental.",
    desc: "Alquiler de equipos",
    href: "/rental",
    bg: "bg-amber",
    fg: "text-ink",
    accent: "text-amber",
  },
  estudio: {
    label: "estudio.",
    desc: "Set de foto y video",
    href: "/estudio",
    bg: "bg-estudio",
    fg: "text-ink",
    accent: "text-estudio",
  },
  workshops: {
    label: "workshops.",
    desc: "Talleres y formación",
    href: "/workshops",
    bg: "bg-rosa",
    fg: "text-ink",
    accent: "text-rosa",
  },
} as const;

export type AreaKey = keyof typeof AREAS;

/** Las áreas como lista, para iterar (menú de navegación). */
export const AREA_LIST = (Object.keys(AREAS) as AreaKey[]).map((key) => ({ key, ...AREAS[key] }));
