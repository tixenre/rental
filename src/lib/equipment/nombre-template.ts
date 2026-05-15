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

export type SpecLike = {
  label: string;
  /** Value formateado para mostrar (texto legible). */
  value: string;
  /** Solo presente para specs tipo tabla: JSON crudo del array de filas.
   *  Sirve para placeholders `{spec:Label.colKey}` que extraen celdas
   *  específicas en lugar del texto completo. */
  value_raw?: string;
};

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

/** Formatea una celda de spec tabla a texto. Soporta valor_unidad
 *  (`{valor, unidad}` → "19389 lm") y escalares ("4K", true, etc). */
function formatTablaCell(cell: unknown): string {
  if (cell == null || cell === "") return "";
  if (typeof cell === "object" && "valor" in (cell as object)) {
    const c = cell as { valor: unknown; unidad?: unknown };
    const valor = c.valor == null ? "" : String(c.valor);
    const unidad = c.unidad ? String(c.unidad).trim() : "";
    return unidad ? `${valor} ${unidad}`.trim() : valor;
  }
  return String(cell).trim();
}

/** Resuelve un placeholder `spec:Label` o `spec:Label.colKey[i]`.
 *  - Sin `.colKey`: si el value es un JSON tabla, ya viene pre-formateado por
 *    backend; lo devolvemos tal cual. Si no, value crudo.
 *  - Con `.colKey`: parsea el value como JSON array y extrae la celda de la
 *    columna `colKey` en la fila `i` (default 0).  */
function lookupSpec(specs: SpecLike[] | undefined, key: string): string {
  if (!specs) return "";
  // Parsear "Label.colKey[i]" o "Label.colKey" o "Label".
  let label = key;
  let colKey: string | null = null;
  let rowIdx = 0;
  const dotIdx = key.indexOf(".");
  if (dotIdx !== -1) {
    label = key.slice(0, dotIdx);
    let rest = key.slice(dotIdx + 1);
    const m = rest.match(/^(.+?)\[(\d+)\]$/);
    if (m) {
      colKey = m[1];
      rowIdx = parseInt(m[2], 10) || 0;
    } else {
      colKey = rest;
    }
  }
  const target = normalizeLabel(label);
  const found = specs.find((s) => normalizeLabel(s.label) === target);
  if (!found) return "";
  if (!colKey) {
    // Sin selector de columna: value tal cual (ya viene legible).
    return normalizePrefixUnitValue((found.value ?? "").trim());
  }
  // Con selector de columna: usar value_raw (JSON crudo) si está, o
  // fallback al value si parece JSON. Extraer la celda colKey de la fila i.
  const rawSource = found.value_raw ?? found.value ?? "";
  const raw = rawSource.trim();
  if (!raw.startsWith("[") && !raw.startsWith("{")) return "";
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || rowIdx >= parsed.length) return "";
    const row = parsed[rowIdx];
    if (!row || typeof row !== "object") return "";
    return formatTablaCell((row as Record<string, unknown>)[colKey]);
  } catch {
    return "";
  }
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
