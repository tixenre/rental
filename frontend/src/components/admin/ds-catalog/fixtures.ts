/**
 * fixtures — dataset demo CANÓNICO de la vitrina del DS.
 *
 * Una sola fuente de "datos de ejemplo" para todos los specimens: en vez de que
 * cada sección invente su propio mock, todas importan de acá. Así la vitrina
 * muestra **los mismos escenarios** en todas partes (un equipo simple, un kit,
 * un combo; un cliente verificado y uno sin verificar; un pedido sin iniciar,
 * presupuestado, confirmado y pagado; una lista guardada) y se ve de un vistazo
 * cómo se comporta cada organismo ante cada estado.
 *
 * Tipado contra los tipos REALES del dominio (no formas inventadas) → si un tipo
 * cambia, el typecheck rompe acá y se actualiza en un solo lugar.
 *
 * NO es para producción: son datos ficticios con ids fuera del rango real. La
 * idea es que mañana un `seed_demo.py` siembre estos mismos escenarios en un
 * Postgres local — mismas variantes, dos representaciones (TS para la vitrina,
 * SQL para el server local).
 */
import { type Equipment, type IncludedItem } from "@/data/equipment";

/** Callback vacío para specimens que no necesitan reaccionar. */
export const noop = () => {};

// ────────────────────────────────────────────────────────────────────────────
// EQUIPOS — las tres formas del producto (A1 #635: simple · kit · combo)
// ────────────────────────────────────────────────────────────────────────────

/** Lo que trae el kit FX6 — reusado por IncludesLine / AddonPills / el card. */
export const includesDemo: IncludedItem[] = [
  { name: "Cuerpo FX6" },
  { name: "Batería BP-U60", qty: 2 },
  { name: "Cargador" },
  { name: "Asa XLR" },
  { name: "Correa" },
];

/**
 * Equipo SIMPLE — un solo ítem, sin composición. Sin foto a propósito, para
 * que el card muestre el EmptyImage (placeholder de categoría).
 */
export const equipoSimple: Equipment = {
  id: "9001",
  slug: "demo-sigma-24-70",
  name: "Sigma 24-70 f/2.8 DG DN",
  brand: "Sigma",
  category: "Lentes",
  pricePerDay: 18500,
  description: "Zoom estándar profesional para montura E. Equipo de muestra (simple).",
  tipo: "simple",
  cantidad: 3,
  fotoUrl: null,
  specs: [
    { label: "Distancia focal", value: "24-70mm" },
    { label: "Apertura", value: "f/2.8" },
    { label: "Montura", value: "Sony E" },
  ],
  specsDestacados: [
    { label: "Apertura", value: "f/2.8" },
    { label: "Focal", value: "24-70mm" },
  ],
  _backendId: 9001,
};

/**
 * Equipo KIT — un cuerpo armado con sus accesorios (`includes`). Destacado
 * (badge "destacado") y con dos specs marcadas para que SpecsGrid las cure.
 */
export const equipoKit: Equipment = {
  id: "9002",
  slug: "demo-sony-fx6",
  name: "FX6 Cinema Line",
  brand: "Sony",
  category: "Cámaras",
  pricePerDay: 38000,
  description: "Cámara cine full-frame, armada como kit listo para rodar. Equipo de muestra (kit).",
  tipo: "kit",
  cantidad: 2,
  destacado: true,
  relevanciaManual: 20,
  includes: includesDemo,
  specs: [
    { label: "Sensor", value: "Full-frame 10.2MP" },
    { label: "Montura", value: "E-mount" },
    { label: "ISO", value: "409600" },
    { label: "Formato", value: "4K 120p" },
  ],
  specsRaw: {
    sensor: {
      label: "Sensor",
      value: "Full-frame 10.2MP",
      tipo: "texto",
      unidad: null,
      prioridad: 1,
      en_card: true,
      en_filtros: false,
      destacado: true,
    },
    formato: {
      label: "Formato",
      value: "4K 120p",
      tipo: "texto",
      unidad: null,
      prioridad: 2,
      en_card: true,
      en_filtros: false,
      destacado: true,
    },
  },
  _backendId: 9002,
};

/**
 * Equipo COMBO — paquete de varios equipos con ítems `esencial` (true) y
 * best-effort (false). Sin stock múltiple (cantidad 1).
 */
export const equipoCombo: Equipment = {
  id: "9003",
  slug: "demo-combo-entrevista",
  name: "Combo Entrevista · 2 Cámaras",
  brand: "Rambla",
  category: "Cámaras",
  pricePerDay: 92000,
  description: "Combo listo para entrevista: 2 cuerpos + luces + audio. Equipo de muestra (combo).",
  tipo: "combo",
  cantidad: 1,
  destacado: true,
  includes: [
    { name: "Sony FX3 Cuerpo", qty: 2, esencial: true },
    { name: "Aputure 300X Bi-color", qty: 2, esencial: true },
    { name: "Rode Wireless GO II", esencial: true },
    { name: "Trípode Manfrotto 504X", qty: 2, esencial: false },
    { name: "CFexpress 512GB", qty: 2, esencial: false },
  ],
  specs: [
    { label: "Incluye", value: "2 cuerpos + luces + audio" },
    { label: "Ideal para", value: "Entrevistas / contenido" },
  ],
  _backendId: 9003,
};

/** Las tres variantes juntas — para grids que muestran "las tres formas". */
export const equiposDemo: Equipment[] = [equipoSimple, equipoKit, equipoCombo];
