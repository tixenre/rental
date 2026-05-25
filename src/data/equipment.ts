// Nombre de categoría — ahora es el nombre literal del backend (tabla `categorias`).
// Se mantiene como string para soportar cualquier nombre que el admin cree.
// La inferencia por keywords se usa solo como fallback para equipos sin categoría asignada.
export type Category = string;

export type IncludedItem = {
  /** Si está y matchea con un equipo del catálogo, se enriquece con su info. */
  id?: string;
  name: string;
  qty?: number;
  note?: string;
  fotoUrl?: string | null;
};

/** Ref a una categoría asignada al equipo via M2M `equipo_categorias`.
 *  El backend devuelve la lista completa — el frontend usa `category`
 *  (singular, root) como fallback y `categorias` para filtrar por sub-cats. */
export type CategoryRef = {
  id: number;
  nombre: string;
  parent_id: number | null;
};

export type Equipment = {
  id: string; // string-ificado del ID numérico del backend
  slug: string;
  name: string;
  brand: string;
  category: Category;
  /** Lista completa de categorías asignadas (root + sub) desde `equipo_categorias`.
   *  Vacía cuando el equipo todavía no fue clasificado. */
  categorias?: CategoryRef[];
  pricePerDay: number;
  description: string;
  specs: {
    label: string;
    value: string;
    value_raw?: string;
    output_config?: { row_strategy?: "all" | "first" | "last" } | null;
  }[];
  /** Specs marcadas como destacado en el template de la categoría. Se usan
   *  como "quick facts" en la fila del catálogo. Vacío → fallback a montura/
   *  formato/resolución hardcodeados. */
  specsDestacados?: { label: string; value: string }[];
  /** Palabras clave editoriales (selling points) — distintas de las etiquetas de búsqueda. */
  keywords?: string[];
  // Campos de Lovable
  isNew?: boolean;
  /** True si relevancia_manual ≤ 30 (flagship/premium). Aparece como
   *  badge "destacado" en el card del catálogo. */
  destacado?: boolean;
  /** Copia del relevancia_manual del backend (menor = más importante). Default 100. */
  relevanciaManual?: number;
  includes?: IncludedItem[];
  // Campos extra del backend (opcionales para mantener compat con datos locales)
  fotoUrl?: string | null;
  cantidad?: number; // stock total
  _backendId?: number; // ID numérico original, para POST /api/alquileres
  // Ficha técnica extendida (enriquecida desde Firecrawl + IA)
  peso?: string | null;
  dimensiones?: string | null;
  montura?: string | null;
  formato?: string | null;
  resolucion?: string | null;
  alimentacion?: string | null;
  incluye?: string[];
  conectividad?: string[];
  compatibleCon?: string[];
  videoUrl?: string | null;
  precioBhUsd?: number | null;
  /** Unidades disponibles para el rango de fechas pedido. Solo presente cuando se consulta con fechas. */
  disponible?: number;
  /** Dict raw de specs estructuradas keyed por spec_key (Fase H: filtros
   *  públicos dinámicos). Cada entry tiene la metadata del template
   *  necesaria para construir UI de filtros: {value, label, tipo,
   *  prioridad, en_filtros, en_card, destacado}. */
  specsRaw?: Record<
    string,
    {
      label: string;
      value: string;
      tipo: string;
      unidad: string | null;
      prioridad: number;
      en_card: boolean;
      en_filtros: boolean;
      destacado: boolean;
    }
  >;
};

const e = (
  id: string,
  brand: string,
  name: string,
  category: Category,
  pricePerDay: number,
  description: string,
  specs: { label: string; value: string }[],
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
});

export const equipment: Equipment[] = [
  // Cámaras
  e(
    "c1",
    "Sony",
    "FX3 Cuerpo",
    "Cámaras",
    95000,
    "Cámara cinema full-frame compacta con sensor retroiluminado.",
    [
      { label: "Sensor", value: "Full-frame 10.2MP" },
      { label: "Montura", value: "Sony E" },
      { label: "Video", value: "4K 120p / S-Log3" },
    ],
  ),
  e(
    "c2",
    "Sony",
    "A7S III Cuerpo",
    "Cámaras",
    75000,
    "Sensibilidad ISO extrema, ideal para baja luz.",
    [
      { label: "Sensor", value: "Full-frame 12MP" },
      { label: "Video", value: "4K 120p 10-bit" },
    ],
  ),
  e("c3", "Canon", "C70 Cuerpo", "Cámaras", 110000, "Cinema EOS Super35 con DGO.", [
    { label: "Sensor", value: "Super35 DGO" },
    { label: "Montura", value: "Canon RF" },
  ]),
  e("c4", "Blackmagic", "Pocket 6K G2", "Cámaras", 65000, "Super35 con grabación BRAW interna.", [
    { label: "Sensor", value: "Super35 6K" },
    { label: "Montura", value: "EF" },
  ]),
  e("c5", "Canon", "R5 C", "Cámaras", 85000, "Híbrida foto/cine 8K RAW.", [
    { label: "Sensor", value: "Full-frame 45MP" },
    { label: "Video", value: "8K 30p RAW" },
  ]),
  e(
    "c6",
    "DJI",
    "Ronin 4D 6K",
    "Cámaras",
    180000,
    "Sistema cine integrado con estabilización 4 ejes.",
    [{ label: "Sensor", value: "Full-frame 6K" }],
  ),

  // Lentes
  e(
    "l1",
    "Sigma",
    "24-70 f/2.8 DG DN E",
    "Lentes",
    18500,
    "Zoom estándar profesional para Sony E.",
    [
      { label: "Distancia", value: "24-70mm" },
      { label: "Apertura", value: "f/2.8" },
    ],
  ),
  e("l2", "Sigma", "18-35 f/1.8 EF", "Lentes", 16000, "Zoom luminoso clásico para Super35.", [
    { label: "Distancia", value: "18-35mm" },
    { label: "Apertura", value: "f/1.8" },
  ]),
  e("l3", "Canon", "RF 24-70 f/2.8L", "Lentes", 22000, "Zoom estándar L-series.", [
    { label: "Apertura", value: "f/2.8 IS" },
  ]),
  e("l4", "Canon", "RF 70-200 f/2.8L", "Lentes", 24000, "Telezoom L-series compacto.", [
    { label: "Apertura", value: "f/2.8 IS" },
  ]),
  e("l5", "Sony", "GM 35mm f/1.4", "Lentes", 17500, "Prime gran angular G Master.", [
    { label: "Distancia", value: "35mm" },
  ]),
  e("l6", "Sony", "GM 85mm f/1.4", "Lentes", 18000, "Prime retrato G Master.", [
    { label: "Distancia", value: "85mm" },
  ]),
  e("l7", "Laowa", "12mm T2.9 Zero-D Cine", "Lentes", 19000, "Ultra gran angular sin distorsión.", [
    { label: "Distancia", value: "12mm" },
  ]),

  // Iluminación
  e(
    "i1",
    "Aputure",
    "300X Bi-color",
    "Iluminación",
    14000,
    "LED COB bicolor 2700-6500K con bowens.",
    [
      { label: "Potencia", value: "350W" },
      { label: "CCT", value: "2700-6500K" },
    ],
  ),
  e("i2", "Aputure", "600D Pro", "Iluminación", 22000, "LED COB daylight de alta potencia.", [
    { label: "Potencia", value: "600W" },
  ]),
  e("i3", "Aputure", "Nova P300c", "Iluminación", 28000, "Panel RGBWW con efectos integrados.", [
    { label: "Tipo", value: "RGBWW" },
  ]),
  e("i4", "Godox", "SL-150W II", "Iluminación", 8500, "LED COB daylight económico y confiable.", [
    { label: "Potencia", value: "150W" },
  ]),
  e("i5", "Nanlite", "Forza 500", "Iluminación", 16000, "LED COB compacto con FX.", [
    { label: "Potencia", value: "500W" },
  ]),
  e(
    "i6",
    "Kino Flo",
    "Diva-Lite 401",
    "Iluminación",
    12000,
    "Panel fluorescente clásico bicolor.",
    [{ label: "Tipo", value: "Fluorescente bicolor" }],
  ),
  e("i7", "Amaran", "200X S Bi-color", "Iluminación", 7500, "LED COB compacto bicolor.", [
    { label: "Potencia", value: "200W" },
  ]),

  // Audio
  e("a1", "Rode", "NTG-3 Shotgun", "Audio", 6500, "Micrófono direccional de referencia.", [
    { label: "Tipo", value: "Shotgun condenser" },
  ]),
  e("a2", "Sony", "UWP-D21 Lavalier", "Audio", 7000, "Sistema inalámbrico de solapa UHF.", [
    { label: "Banda", value: "UHF" },
  ]),
  e("a3", "Rode", "Wireless GO II", "Audio", 5500, "Sistema inalámbrico digital de bolsillo.", [
    { label: "Canales", value: "2" },
  ]),

  // Soportes
  e("s1", "Manfrotto", "504X Trípode", "Soportes", 6500, "Trípode video con cabezal fluido.", [
    { label: "Cabezal", value: "504X" },
  ]),
  e(
    "s2",
    "Manfrotto",
    "Magic Arm + Super Clamp",
    "Soportes",
    1800,
    "Brazo articulado para rigging.",
    [],
  ),
  e("s3", "Avenger", "C-Stand C1510", "Soportes", 1500, "Pie C clásico con barra y cabezal.", []),
  e("s4", "Avenger", "C-Stand C4462", "Soportes", 1500, "Pie C corto con base plegable.", []),
  e(
    "s5",
    "Avenger",
    "Roller Stand E390",
    "Soportes",
    500,
    "Pie con ruedas para iluminación pesada.",
    [],
  ),
  e(
    "s6",
    "Glidecam",
    "HD-4000",
    "Soportes",
    8500,
    "Estabilizador mecánico para cámaras medianas.",
    [],
  ),
  e(
    "s7",
    "Edelkrone",
    "SliderPLUS V5",
    "Soportes",
    9500,
    "Slider compacto con doble recorrido.",
    [],
  ),

  // Accesorios
  e(
    "ac1",
    "Hollyland",
    "Mars 400S Pro",
    "Accesorios",
    7500,
    "Transmisión de video inalámbrica HD.",
    [],
  ),
  e("ac2", "Atomos", "Ninja V Monitor", "Accesorios", 8500, 'Monitor-grabador 5" 4K HDR.', []),
  e("ac3", "Lilliput", 'A7S Monitor 7"', "Accesorios", 4500, "Monitor de campo 7 pulgadas.", []),
  e(
    "ac4",
    "Angelbird",
    "AV Pro CFexpress 512GB",
    "Accesorios",
    3500,
    "Tarjeta CFexpress de alto rendimiento.",
    [],
  ),
  e("ac5", "Canon", "Batería LP-E6", "Accesorios", 5500, "Batería original Canon.", []),
  e(
    "ac6",
    "Backdrop",
    "Fondo Negro 3x6m",
    "Accesorios",
    13500,
    "Fondo de tela negro con trípodes y barral.",
    [],
  ),
  e("ac7", "Matthews", "Bandera Negra 60x90cm", "Accesorios", 2500, "Bandera black solid.", []),
  e(
    "ac8",
    "Matthews",
    "Bandera Negra 35x40cm",
    "Accesorios",
    2500,
    "Bandera black solid pequeña.",
    [],
  ),
  e(
    "ac9",
    "Impact",
    'Baby Pin Wall Plate 3"',
    "Accesorios",
    500,
    'Plate de pared con baby pin 5/8".',
    [],
  ),
  e(
    "ac10",
    "Impact",
    'Baby Pin Wall Plate 6"',
    "Accesorios",
    500,
    "Plate de pared con baby pin extendido.",
    [],
  ),
  e(
    "ac11",
    "Pampa",
    "Alargue Eléctrico 25m",
    "Accesorios",
    1500,
    "Alargue eléctrico profesional.",
    [],
  ),
  e(
    "ac12",
    "DJI",
    "RS 3 Pro Gimbal",
    "Accesorios",
    14000,
    "Estabilizador para cámaras cinema.",
    [],
  ),

  // Adaptadores
  e("ad1", "Canon", "Adaptador EF-RF", "Adaptadores", 20500, "Adaptador original sin filtro.", []),
  e(
    "ad2",
    "Sigma",
    "Adaptador EF-E MC-11",
    "Adaptadores",
    8500,
    "Adaptador EF a Sony E con AF.",
    [],
  ),
  e(
    "ad3",
    "Canon",
    "Adaptador EF-RF con ND Variable",
    "Adaptadores",
    13500,
    "Adaptador con drop-in ND variable.",
    [],
  ),
  e(
    "ad4",
    "Canon",
    "Adaptador EF-RF Speedbooster",
    "Adaptadores",
    20500,
    "Speedbooster óptico.",
    [],
  ),
  e(
    "ad5",
    "Rambla",
    "Adaptador M42 a Montura E",
    "Adaptadores",
    2500,
    "Adaptador mecánico clásico.",
    [],
  ),
];

export const categories: Category[] = [
  "Cámaras",
  "Lentes",
  "Iluminación",
  "Audio",
  "Soportes",
  "Accesorios",
  "Adaptadores",
];

export const brands = Array.from(new Set(equipment.map((x) => x.brand))).sort();

export const formatPrice = (n: number) =>
  new Intl.NumberFormat("es-AR", { maximumFractionDigits: 0 }).format(n);
