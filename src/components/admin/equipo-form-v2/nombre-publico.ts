/**
 * Auto-generación de nombre público por categoría raíz.
 *
 * El "nombre interno" es técnico para inventario (ej. "Sony ILME-FX30B Cuerpo").
 * El "nombre público" es lo que ve el cliente en el catálogo
 * (ej. "Cámara Sony FX30 Montura E Super 35").
 *
 * Auto-gen funciona bien para categorías con campos predecibles (marca + modelo
 * + montura/formato). Para cables/accesorios donde el nombre depende de la spec
 * dominante (longitud, tipo de conector), el usuario escribe a mano.
 *
 * Si una categoría no tiene template, generar() devuelve null y la UI
 * deja el toggle "auto" desactivado.
 */

export interface NombrePublicoVars {
  marca: string;
  modelo: string;
  montura: string;
  formato: string;
  resolucion: string;
}

type TemplateFn = (v: NombrePublicoVars) => string;

/**
 * Templates indexados por nombre de la categoría raíz (case-insensitive, sin
 * acentos). El orden de campos en la salida es el que el usuario quiere ver
 * en el catálogo.
 *
 * Para agregar una categoría nueva: agregar entrada acá. No tocar el componente.
 */
const TEMPLATES: Record<string, TemplateFn> = {
  camaras: (v) => join("Cámara", v.marca, v.modelo, monturaConPrefijo(v.montura), v.formato),
  lentes: (v) => join("Lente", v.marca, v.modelo, monturaConPrefijo(v.montura)),
  iluminacion: (v) => join("Luz", v.marca, v.modelo),
  audio: (v) => join("Audio", v.marca, v.modelo),
  "tripodes y soportes": (v) => join("Trípode", v.marca, v.modelo),
  tripodes: (v) => join("Trípode", v.marca, v.modelo),
  estabilizadores: (v) => join("Estabilizador", v.marca, v.modelo),
  monitores: (v) => join("Monitor", v.marca, v.modelo, v.resolucion),
  grabadores: (v) => join("Grabador", v.marca, v.modelo),
};

function normalizeKey(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

function monturaConPrefijo(montura: string): string {
  const m = montura.trim();
  if (!m) return "";
  // Si ya empieza con "Montura", no duplicar.
  if (/^montura\b/i.test(m)) return m;
  return `Montura ${m}`;
}

function join(...parts: string[]): string {
  return parts
    .map((p) => p.trim())
    .filter(Boolean)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Genera el nombre público a partir de la categoría raíz + los campos.
 * Devuelve null si la categoría no tiene template definido (el usuario
 * escribe a mano).
 */
export function generarNombrePublico(
  categoriaRoot: string | null | undefined,
  vars: NombrePublicoVars,
): string | null {
  if (!categoriaRoot) return null;
  const fn = TEMPLATES[normalizeKey(categoriaRoot)];
  if (!fn) return null;
  const out = fn(vars).trim();
  return out || null;
}

/** ¿La categoría tiene template definido? */
export function categoriaSoportaAutoGen(categoriaRoot: string | null | undefined): boolean {
  if (!categoriaRoot) return false;
  return normalizeKey(categoriaRoot) in TEMPLATES;
}
