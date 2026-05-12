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
