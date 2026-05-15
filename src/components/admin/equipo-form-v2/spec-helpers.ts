/**
 * Tipos y helpers para specs del form V2.
 * Compartidos entre EquipoFormDialogV2 y SpecsDiffEditor (#207).
 */

export type Spec = { id: string; label: string; value: string };

export const newSpec = (label = "", value = ""): Spec => ({
  id: crypto.randomUUID(),
  label,
  value,
});

export const withIds = (raw: Array<{ label: string; value: string }>): Spec[] =>
  raw.map((s) => newSpec(s.label, s.value));

export const sameLabel = (a: string, b: string) =>
  a.trim().toLowerCase() === b.trim().toLowerCase();

/** Normalización agresiva para match fuzzy: lowercase, sin tildes, sin
 *  paréntesis ni contenido, sin espacios extra. Útil cuando el LLM trae
 *  "FPS max" y el template tiene "FPS máx", o "Megapixels" vs
 *  "Megapixels (efectivos)". */
const normalize = (s: string): string =>
  s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")  // saca tildes/diacríticos
    .replace(/\s*\([^)]*\)\s*/g, " ")  // saca "(...)" y contenido
    .replace(/[._\-\/]/g, " ")          // separadores → espacio
    .replace(/\s+/g, " ")
    .trim();

/** Match fuzzy entre labels: igualdad exacta normalizada, o uno contiene
 *  al otro como palabra (sub-string normalizado). Soporta los típicos
 *  del LLM: "FPS max" ↔ "FPS máx", "Sensor" ↔ "Tipo de sensor",
 *  "Resolucion" ↔ "Resolución máx. de grabación". */
export const fuzzySameLabel = (a: string, b: string): boolean => {
  const na = normalize(a);
  const nb = normalize(b);
  if (!na || !nb) return false;
  if (na === nb) return true;
  // Sub-string solo si la versión "corta" tiene al menos 4 chars (evita
  // que "no" matchee con "nombre" o cosas así). El LLM suele traer labels
  // más cortos que el template (ej. "Formato" vs "Formato de sensor").
  const [short, long] = na.length <= nb.length ? [na, nb] : [nb, na];
  if (short.length < 4) return false;
  return long.includes(short);
};

/** Une dos listas de specs por label (case-insensitive). Si ya existe, no pisa. */
export const mergeSpecs = (existing: Spec[], extras: Spec[]): Spec[] => {
  const result = [...existing];
  for (const e of extras) {
    if (!e.value.trim()) continue;
    if (result.some((s) => sameLabel(s.label, e.label))) continue;
    result.push(e);
  }
  return result;
};

/** Devuelve el valor de un spec por label, o "". */
export const findSpecValue = (specs: Spec[], label: string): string =>
  specs.find((s) => sameLabel(s.label, label))?.value ?? "";

export const uniq = <T,>(arr: T[]): T[] => Array.from(new Set(arr));

/**
 * Para un spec numérico, extrae solo la parte numérica del value persistido.
 * Acepta "2.5", "2,5", "2.5 kg", "2,5 megapíxeles", etc. Devuelve la string
 * del número (sin la unidad). Si no parsea, devuelve "".
 * #291 Fase B: permite que el form renderee solo el número aunque el storage
 * legacy tenga la unidad concatenada.
 */
export const extractNumericPart = (value: string): string => {
  // El número puede venir al principio ("2.8 kg") o después de un prefijo
  // ("f/2.8", "$1500"). Buscamos el primer match en cualquier posición.
  const m = value.trim().match(/[-+]?\d+(?:[.,]\d+)?/);
  return m ? m[0].replace(",", ".") : "";
};
