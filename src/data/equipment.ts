export type Category =
  | "Cámaras"
  | "Lentes"
  | "Monitores"
  | "Luces"
  | "Tungsteno"
  | "Modificadores"
  | "Comunicación"
  | "Flash"
  | "Brazo Mágico"
  | "Stands"
  | "Grips"
  | "Trípode"
  | "Sonido"
  | "Baterías"
  | "Filtros";

export type Equipment = {
  id: string;
  slug: string;
  name: string;
  brand: string;
  category: Category;
  pricePerDay: number;
  description: string;
  isNew?: boolean;
  isCombo?: boolean;
  specs: { label: string; value: string }[];
};

const e = (
  id: string,
  brand: string,
  name: string,
  category: Category,
  pricePerDay: number,
  description: string,
  specs: { label: string; value: string }[] = [],
  flags: { isNew?: boolean; isCombo?: boolean } = {},
): Equipment => ({
  id,
  slug: `${brand}-${name}`
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, ""),
  name,
  brand,
  category,
  pricePerDay,
  description,
  specs,
  ...flags,
});

export const equipment: Equipment[] = [
  // ─── Cámaras ─────────────────────────────────────────
  e("c1", "Red", "Komodo X", "Cámaras", 359000, "Cinema 6K Super35 con global shutter.", [], { isNew: true }),
  e("c2", "Sony", "FX3", "Cámaras", 122500, "Full-frame cinema compacta, S-Log3.", []),
  e("c3", "Sony", "7V", "Cámaras", 97500, "Full-frame híbrida 33MP / 4K.", [], { isNew: true }),
  e("c4", "Sony", "ZVE1", "Cámaras", 72500, "Full-frame compacta para creadores.", []),
  e("c5", "Red", "Komodo", "Cámaras", 140000, "Cinema 6K compacta con RAW.", []),
  e("c6", "Canon", "C200", "Cámaras", 91000, "Cinema EOS Super35 con DGO.", []),
  e("c7", "Insta360", "x4 8K", "Cámaras", 19000, "360º 8K para acción y POV.", []),
  e("c8", "Sony", "FX6", "Cámaras", 165000, "Full-frame cinema con ND eléctrico.", []),

  // ─── Lentes ──────────────────────────────────────────
  e("l1", "Sony", "GM 24-70 f/2.8 vii", "Lentes", 76500, "Zoom estándar G Master.", []),
  e("l2", "Sony", "GM 12-24 f/2.8", "Lentes", 91500, "Ultra gran angular G Master.", []),
  e("l3", "Sony", "GM 70-200 f/2.8", "Lentes", 78000, "Telezoom G Master.", []),
  e("l4", "Sigma", "Art 35mm f/1.4 EF", "Lentes", 28500, "Prime full-frame.", [], { isNew: true }),
  e("l5", "Sigma", "Art 50mm f/1.4 EF", "Lentes", 28500, "Prime estándar full-frame.", []),
  e("l6", "Sigma", "18-35 f/1.8 EF", "Lentes", 32000, "Zoom luminoso Super35.", []),
  e("l7", "Laowa", "Macro Probe 24mm", "Lentes", 56000, "Macro tipo sonda.", []),
  e("l8", "Canon", "RF 24-70 f/2.8L", "Lentes", 64000, "Zoom estándar L-series.", []),

  // ─── Monitores ───────────────────────────────────────
  e("m1", "Atomos", "Ninja V", "Monitores", 22000, "Monitor-grabador 5\" 4K HDR.", []),
  e("m2", "SmallHD", "Cine 7", "Monitores", 36000, "Monitor de campo 7\" 1800 nits.", []),
  e("m3", "Lilliput", "A7s 7\"", "Monitores", 9500, "Monitor de campo 7\".", []),
  e("m4", "Hollyland", "Mars M1", "Monitores", 28000, "Monitor + transmisor inalámbrico.", []),

  // ─── Luces ───────────────────────────────────────────
  e("li1", "Aputure", "300X Bi-color", "Luces", 28000, "LED COB bicolor con bowens.", []),
  e("li2", "Aputure", "600D Pro", "Luces", 38000, "LED COB daylight 600W.", []),
  e("li3", "Nanlite", "Forza 500", "Luces", 32000, "LED COB 500W.", []),
  e("li4", "Amaran", "300C", "Luces", 24500, "LED RGBWW COB con FX.", []),
  e("li5", "Godox", "Tubo TL60", "Luces", 8500, "Tubo RGB 60cm.", []),
  e("li6", "Aputure", "Nova P300c", "Luces", 56000, "Panel RGBWW.", []),
  e("li7", "Aputure", "MC Pro", "Luces", 7800, "Mini panel RGB de bolsillo.", []),

  // ─── Tungsteno ───────────────────────────────────────
  e("t1", "Arri", "Kit Fresnel 3und", "Tungsteno", 90000, "Kit Arri tungsteno 650+300+150W.", []),
  e("t2", "Arri", "Fresnel 1K", "Tungsteno", 38000, "Foco Fresnel 1000W.", []),
  e("t3", "Lowel", "Pro Light", "Tungsteno", 12000, "Tungsteno open-face 250W.", []),

  // ─── Modificadores ───────────────────────────────────
  e("mo1", "Aputure", "Light Dome III", "Modificadores", 9500, "Softbox 90cm bowens.", []),
  e("mo2", "Aputure", "Lantern", "Modificadores", 8500, "Lantern soft 360º.", []),
  e("mo3", "Matthews", "Bandera 60×90 black", "Modificadores", 4500, "Bandera black solid.", []),
  e("mo4", "Matthews", "Bandera 35×40 black", "Modificadores", 3500, "Bandera black solid.", []),
  e("mo5", "Rambla", "Difusor 1.2×1.2 + Frame", "Modificadores", 6500, "Difusor con frame de aluminio.", []),

  // ─── Comunicación ────────────────────────────────────
  e("co1", "Hollyland", "Solidcom C1 4 headsets", "Comunicación", 68000, "Sistema de intercom inalámbrico 1.9 GHz.", [], { isNew: true }),

  // ─── Flash ───────────────────────────────────────────
  e("f1", "Godox", "V100 Flash Sony", "Flash", 20500, "Flash de cámara TTL.", [], { isNew: true }),
  e("f2", "Godox", "AD200 Pro", "Flash", 18000, "Flash portátil 200W.", []),

  // ─── Brazo Mágico ────────────────────────────────────
  e("bm1", "Impact", "Brazo Mágico", "Brazo Mágico", 3500, "Brazo articulado para rigging.", [], { isNew: true }),

  // ─── Stands ──────────────────────────────────────────
  e("st1", "Avenger", "C-Stand 40\"", "Stands", 4500, "C-Stand clásico con barra y cabezal.", []),
  e("st2", "Avenger", "C-Stand corto", "Stands", 4500, "C-Stand corto con base plegable.", []),
  e("st3", "Manfrotto", "Roller Stand", "Stands", 5500, "Pie con ruedas para luces pesadas.", []),
  e("st4", "Avenger", "Lowboy", "Stands", 3500, "Pie bajo para luz a ras de piso.", []),

  // ─── Grips ───────────────────────────────────────────
  e("g1", "Tilta", "Car Mount Hydra 3 ventosas", "Grips", 35000, "Car mount con ventosas eléctricas.", [], { isNew: true }),
  e("g2", "Manfrotto", "Magic Arm + Super Clamp", "Grips", 4500, "Brazo articulado para rigging.", []),
  e("g3", "Matthews", "Super Mafer Clamp", "Grips", 3500, "Clamp profesional.", []),
  e("g4", "Impact", "Baby Pin Plate 3\"", "Grips", 1500, "Plate de pared con baby pin 5/8\".", []),

  // ─── Trípode ─────────────────────────────────────────
  e("tr1", "Manfrotto", "504X + Trípode", "Trípode", 12500, "Trípode video con cabezal fluido.", []),
  e("tr2", "Sachtler", "FSB-8 + Trípode", "Trípode", 22000, "Trípode video pro.", []),
  e("tr3", "Manfrotto", "190 + Bola", "Trípode", 6500, "Trípode foto con cabezal de bola.", []),

  // ─── Sonido ──────────────────────────────────────────
  e("s1", "Rode", "NTG-3 Shotgun", "Sonido", 9500, "Micrófono direccional de referencia.", []),
  e("s2", "Sony", "UWP-D21 Lavalier", "Sonido", 12000, "Sistema inalámbrico de solapa UHF.", []),
  e("s3", "Rode", "Wireless GO II", "Sonido", 9500, "Sistema inalámbrico digital de bolsillo.", []),
  e("s4", "Zoom", "H6 Grabador", "Sonido", 8500, "Grabador portátil 6 pistas.", []),

  // ─── Baterías ────────────────────────────────────────
  e("b1", "Anton Bauer", "VMount 4und + Cargador doble", "Baterías", 36750, "Kit baterías VMount.", []),
  e("b2", "Anton Bauer", "VMount 150Wh", "Baterías", 9500, "Batería VMount unitaria.", []),
  e("b3", "Canon", "LP-E6 (par)", "Baterías", 3500, "Par de baterías originales.", []),

  // ─── Filtros ─────────────────────────────────────────
  e("fi1", "Tiffen", "Set ND + ProMist + PC", "Filtros", 12000, "Set de filtros para lentes.", []),

  // ─── Combos ──────────────────────────────────────────
  e(
    "cm1",
    "Rambla",
    "Combo RGB · Amaran 300 + 2 tubos + C-Stand + Softbox",
    "Luces",
    87900,
    "Kit completo de iluminación RGB para producción.",
    [],
    { isCombo: true },
  ),
  e(
    "cm2",
    "Rambla",
    "Combo Nanlite Forza 500 + Softbox + C-Stand",
    "Luces",
    73450,
    "Kit luz dura con softbox y C-Stand.",
    [],
    { isCombo: true },
  ),
  e(
    "cm3",
    "Rambla",
    "Combo Evento · Sony ZVE1 + GM 24/70 vii",
    "Cámaras",
    128025,
    "Kit listo para cobertura de evento.",
    [],
    { isCombo: true },
  ),
  e(
    "cm4",
    "Rambla",
    "Monitor de Producción + Monitoreo Inalámbrico",
    "Monitores",
    81450,
    "Set completo de monitoreo en producción.",
    [],
    { isCombo: true },
  ),
  e(
    "cm5",
    "Rambla",
    "Combo Macro · FX3 + Laowa Macro + Forza 500",
    "Cámaras",
    227700,
    "Kit macro cinematográfico.",
    [],
    { isCombo: true },
  ),
  e(
    "cm6",
    "Rambla",
    "Trío Sony GM · 12/24 + 24/70 + 70/200",
    "Lentes",
    226100,
    "Set completo de zooms G Master.",
    [],
    { isCombo: true },
  ),
];

export const categories: Category[] = [
  "Cámaras",
  "Lentes",
  "Monitores",
  "Luces",
  "Tungsteno",
  "Modificadores",
  "Comunicación",
  "Flash",
  "Brazo Mágico",
  "Stands",
  "Grips",
  "Trípode",
  "Sonido",
  "Baterías",
  "Filtros",
];

export const brands = Array.from(new Set(equipment.map((x) => x.brand))).sort();

/** Legacy helper; prefer `formatARS` from `@/lib/format`. */
export const formatPrice = (n: number) =>
  new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 }).format(n);
