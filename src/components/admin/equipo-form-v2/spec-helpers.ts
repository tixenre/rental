/**
 * Tipos y helpers para specs del form V2.
 * Compartidos entre EquipoFormDialogV2 y SpecsDiffEditor (#207).
 */

export type Spec = { id: string; label: string; value: string; spec_key?: string };

export const newSpec = (label = "", value = "", spec_key?: string): Spec => ({
  id: crypto.randomUUID(),
  label,
  value,
  ...(spec_key ? { spec_key } : {}),
});

export const withIds = (raw: Array<{ label: string; value: string; spec_key?: string }>): Spec[] =>
  raw.map((s) => newSpec(s.label, s.value, s.spec_key));

export const sameLabel = (a: string, b: string) =>
  a.trim().toLowerCase() === b.trim().toLowerCase();

/** Devuelve el valor de un spec por label, o "". */
export const findSpecValue = (specs: Spec[], label: string): string =>
  specs.find((s) => sameLabel(s.label, label))?.value ?? "";

export const uniq = <T>(arr: T[]): T[] => Array.from(new Set(arr));

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
