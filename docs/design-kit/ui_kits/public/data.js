/* Fake catalog data — public-name style ("Cámara Sony FX3 Montura E").
 * Mirrors the auto-generated name template from
 * src/components/admin/equipo-form-v2/nombre-publico.ts.
 */
const CATEGORIES = [
  "Cámaras",
  "Lentes",
  "Iluminación",
  "Audio",
  "Soportes",
  "Accesorios",
  "Adaptadores",
];

const BRANDS = [
  { nombre: "Sony",      icon: "sony" },
  { nombre: "Canon",     icon: "canon" },
  { nombre: "Nikon",     icon: "nikon" },
  { nombre: "Fujifilm",  icon: "fujifilm" },
  { nombre: "Aputure",   icon: null },
  { nombre: "Sennheiser",icon: "sennheiser" },
  { nombre: "Rode",      icon: null },
  { nombre: "DJI",       icon: "dji" },
  { nombre: "Manfrotto", icon: "manfrotto" },
  { nombre: "Sachtler",  icon: null },
  { nombre: "Tilta",     icon: null },
  { nombre: "SmallRig",  icon: null },
];

const EQUIPMENT = [
  // Cámaras — "Cámara <marca> <modelo> Montura <m> <formato>"
  { id: "e1", category: "Cámaras", brand: "Sony",     name: "Cámara Sony FX3 Montura E Full-Frame",        pricePerDay: 38000, isNew: true,  destacado: true,  cantidad: 2 },
  { id: "e2", category: "Cámaras", brand: "Sony",     name: "Cámara Sony A7S III Montura E Full-Frame",    pricePerDay: 28000, isNew: false, destacado: false, cantidad: 3 },
  { id: "e3", category: "Cámaras", brand: "Canon",    name: "Cámara Canon C70 Montura RF Super 35",        pricePerDay: 32000, isNew: false, destacado: true,  cantidad: 1 },
  { id: "e4", category: "Cámaras", brand: "Canon",    name: "Cámara Canon R5 C Montura RF Full-Frame",     pricePerDay: 30000, isNew: true,  destacado: false, cantidad: 2 },
  { id: "e5", category: "Cámaras", brand: "Fujifilm", name: "Cámara Fujifilm X-H2S Montura X APS-C",        pricePerDay: 22000, isNew: false, destacado: false, cantidad: 0 },
  { id: "e6", category: "Cámaras", brand: "DJI",      name: "Cámara DJI Ronin 4D Montura DL Full-Frame",   pricePerDay: 56000, isNew: false, destacado: true,  cantidad: 1 },
  // Lentes
  { id: "l1", category: "Lentes",  brand: "Sony",  name: "Lente Sony GM 24-70mm f/2.8 II Montura E",  pricePerDay: 18000, isNew: false, destacado: true,  cantidad: 2 },
  { id: "l2", category: "Lentes",  brand: "Sony",  name: "Lente Sony GM 70-200mm f/2.8 Montura E",     pricePerDay: 22000, isNew: false, destacado: false, cantidad: 2 },
  { id: "l3", category: "Lentes",  brand: "Canon", name: "Lente Canon RF 24-70mm f/2.8 L Montura RF",  pricePerDay: 17500, isNew: false, destacado: false, cantidad: 2 },
  { id: "l4", category: "Lentes",  brand: "Canon", name: "Lente Canon RF 50mm f/1.2 L Montura RF",     pricePerDay: 15000, isNew: true,  destacado: false, cantidad: 1 },
  { id: "l5", category: "Lentes",  brand: "Sony",  name: "Lente Sony GM 35mm f/1.4 Montura E",         pricePerDay: 14000, isNew: false, destacado: false, cantidad: 1 },
  { id: "l6", category: "Lentes",  brand: "Sony",  name: "Lente Sony GM 16-35mm f/2.8 Montura E",      pricePerDay: 19000, isNew: false, destacado: false, cantidad: 2 },
  // Iluminación — "Luz <marca> <modelo>"
  { id: "i1", category: "Iluminación", brand: "Aputure", name: "Luz Aputure 600x Pro Bicolor",          pricePerDay: 18000, isNew: false, destacado: true,  cantidad: 0 },
  { id: "i2", category: "Iluminación", brand: "Aputure", name: "Luz Aputure 300d Mark II Daylight",      pricePerDay: 9500,  isNew: false, destacado: false, cantidad: 3 },
  { id: "i3", category: "Iluminación", brand: "Aputure", name: "Luz Aputure Nova P300c RGB",             pricePerDay: 14000, isNew: true,  destacado: false, cantidad: 2 },
  { id: "i4", category: "Iluminación", brand: "Aputure", name: "Luz Aputure MC RGB · pack de 4",         pricePerDay: 6500,  isNew: false, destacado: false, cantidad: 2 },
  // Audio — "Audio <marca> <modelo>"
  { id: "a1", category: "Audio", brand: "Sennheiser", name: "Audio Sennheiser MKH 416 Shotgun",         pricePerDay: 11000, isNew: false, destacado: true,  cantidad: 2 },
  { id: "a2", category: "Audio", brand: "Rode",       name: "Audio Rode Wireless Pro · kit completo",    pricePerDay: 6500,  isNew: true,  destacado: false, cantidad: 3 },
  { id: "a3", category: "Audio", brand: "Sennheiser", name: "Audio Sennheiser G4 Lavalier",              pricePerDay: 5500,  isNew: false, destacado: false, cantidad: 4 },
  // Soportes — "Trípode <marca> <modelo>"
  { id: "s1", category: "Soportes", brand: "Sachtler",  name: "Trípode Sachtler FSB 8 + patas Flowtech", pricePerDay: 8500, isNew: false, destacado: false, cantidad: 2 },
  { id: "s2", category: "Soportes", brand: "Manfrotto", name: "Trípode Manfrotto 504X + slider",         pricePerDay: 6800, isNew: false, destacado: false, cantidad: 1 },
  { id: "s3", category: "Soportes", brand: "DJI",       name: "Estabilizador DJI Ronin RS3 Pro",         pricePerDay: 9500, isNew: false, destacado: true,  cantidad: 1 },
  // Accesorios
  { id: "ac1", category: "Accesorios", brand: "SmallRig", name: "Cage SmallRig para Sony FX3",            pricePerDay: 2500, isNew: false, destacado: false, cantidad: 2 },
  { id: "ac2", category: "Accesorios", brand: "Tilta",    name: "Matte box Tilta Mini Clamp-on 4×5.65",   pricePerDay: 3500, isNew: false, destacado: false, cantidad: 1 },
  { id: "ac3", category: "Accesorios", brand: "Tilta",    name: "Filtro Tilta ND 3-stop · 4×5.65",        pricePerDay: 1500, isNew: false, destacado: false, cantidad: 3 },
];

const formatARS = (n) => "$ " + new Intl.NumberFormat("es-AR").format(Math.round(n));

Object.assign(window, { CATEGORIES, BRANDS, EQUIPMENT, formatARS });
