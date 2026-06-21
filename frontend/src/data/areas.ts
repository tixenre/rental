// ── Áreas de Rambla — fuente única ─────────────────────────────────────────────
// Las 3 áreas públicas con su identidad de marca. La consumen el TopBar
// (SECTION_CONFIG), el menú de navegación (AreaMenu) y el hub. Cambiar el color,
// la ruta o el label de un área se hace acá una sola vez.
//
// - `label`: nombre con punto, font-display lowercase ("rental.")
// - `desc`:  bajada corta (menú de áreas)
// - `href`:  root del área
// - `bg`:    clase de fondo de marca
// - `fg`:    color de texto legible sobre `bg` (para piezas con texto sobre el color)

export const AREAS = {
  rental: {
    label: "rental.",
    desc: "Alquiler de equipos",
    href: "/catalogo",
    bg: "bg-amber",
    fg: "text-ink",
  },
  estudio: {
    label: "estudio.",
    desc: "Set de foto y video",
    href: "/estudio",
    bg: "bg-naranja",
    fg: "text-white",
  },
  workshops: {
    label: "workshops.",
    desc: "Talleres y formación",
    href: "/talleres",
    bg: "bg-rosa",
    fg: "text-ink",
  },
} as const;

export type AreaKey = keyof typeof AREAS;

/** Las áreas como lista, para iterar (menú de navegación). */
export const AREA_LIST = (Object.keys(AREAS) as AreaKey[]).map((key) => ({ key, ...AREAS[key] }));
