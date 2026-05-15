/**
 * Renderiza una plantilla de nombre público a partir de los datos del equipo.
 *
 * Sintaxis de placeholders:
 *   {marca}        → equipo.marca
 *   {modelo}       → equipo.modelo
 *   {tipo}         → nombre de la categoría raíz
 *   {nombre}       → equipo.nombre (interno)
 *   {spec:Label}   → valor del spec con ese label (case-insensitive, sin acentos)
 *
 * Si un placeholder no resuelve, queda como string vacío y los separadores
 * adyacentes se colapsan (no quedan "  ·  " feos).
 *
 * Ejemplo:
 *   template: "Cámara {marca} {modelo} {spec:Montura}"
 *   equipo:   { marca: "Sony", modelo: "FX3", specs: [{ label: "Montura", value: "E" }] }
 *   output:   "Cámara Sony FX3 E"
 */

export type SpecLike = { label: string; value: string };

export type NombreTemplateVars = {
  marca?: string | null;
  modelo?: string | null;
  nombre?: string | null;
  /** Nombre de la categoría raíz (para {tipo}). */
  tipo?: string | null;
  specs?: SpecLike[];
};

function normalizeLabel(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

/** Algunas unidades se escriben antes del número (f/, $, €). Si el value
 *  legacy fue guardado como "2.8 f/" (sufijo), lo reformateamos a "f/2.8"
 *  para mostrar la convención correcta en el nombre público.
 *  Solo aplica cuando detectamos la unidad termina en "/" o empieza con
 *  un símbolo monetario. */
function normalizePrefixUnitValue(raw: string): string {
  const trimmed = raw.trim();
  // Match: "<number(-number)?> <unit>" donde unit es prefijo por convención.
  const m = /^(\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?)\s+(\S+)$/.exec(trimmed);
  if (!m) return trimmed;
  const num = m[1];
  const unit = m[2];
  const isPrefix = unit.endsWith("/") || /^[$€£¥]/.test(unit);
  return isPrefix ? `${unit}${num}` : trimmed;
}

function lookupSpec(specs: SpecLike[] | undefined, label: string): string {
  if (!specs) return "";
  const target = normalizeLabel(label);
  const found = specs.find((s) => normalizeLabel(s.label) === target);
  if (!found) return "";
  return normalizePrefixUnitValue((found.value ?? "").trim());
}

/**
 * Render del template. Devuelve el nombre generado o null si el template
 * está vacío.
 */
export function renderNombrePublicoTemplate(
  template: string | null | undefined,
  vars: NombreTemplateVars,
): string | null {
  const tpl = (template ?? "").trim();
  if (!tpl) return null;

  // Reemplaza {placeholder} por su valor (o "").
  const replaced = tpl.replace(/\{([^}]+)\}/g, (_match, raw: string) => {
    const key = raw.trim();
    if (key.startsWith("spec:")) {
      return lookupSpec(vars.specs, key.slice("spec:".length));
    }
    switch (key.toLowerCase()) {
      case "marca": return (vars.marca ?? "").trim();
      case "modelo": return (vars.modelo ?? "").trim();
      case "tipo": return (vars.tipo ?? "").trim();
      case "nombre": return (vars.nombre ?? "").trim();
      default: return "";
    }
  });

  // Colapsar separadores adyacentes que quedan vacíos:
  //   "Cámara  · "  → "Cámara"
  //   "Cámara · ·"  → "Cámara"
  const cleaned = replaced
    .replace(/\s+/g, " ")            // múltiples espacios → uno
    .replace(/\s*·\s*·+\s*/g, " · ") // bullets duplicados
    .replace(/\s*·\s*$/g, "")        // bullet final
    .replace(/^\s*·\s*/g, "")        // bullet inicial
    .trim();

  return cleaned || null;
}

/**
 * Lista de placeholders disponibles para mostrar en el UI de edición.
 * Estáticos + dinámicos (specs de esa categoría).
 */
export function availablePlaceholders(specLabels: string[] = []): string[] {
  const dynamics = specLabels.map((l) => `{spec:${l}}`);
  return ["{marca}", "{modelo}", "{tipo}", "{nombre}", ...dynamics];
}
