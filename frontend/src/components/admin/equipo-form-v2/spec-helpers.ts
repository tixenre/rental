/**
 * Tipos y helpers para specs del form V2.
 * Compartidos entre EquipoFormDialogV2 y SpecsDiffEditor (#207).
 */
import type { SpecTemplate } from "@/lib/admin/api";

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

export const uniq = <T>(arr: T[]): T[] => Array.from(new Set(arr));

/**
 * Busca el template que corresponde a un spec extraído/propuesto —
 * por `spec_key` primero, por label (case/trim-insensitive) como fallback.
 * Extraído de la lógica que EquipoFormDialogV2 duplicaba dos veces
 * (auto-aplicar specs extraídas del HTML, y aceptar una propuesta) — mismo
 * shape, distinto nombre de variable en cada lado.
 */
export const findTemplateMatch = (
  templateItems: SpecTemplate[] | undefined,
  spec: { label: string; spec_key?: string },
): SpecTemplate | undefined => {
  const byKey = new Map<string, SpecTemplate>();
  const byLabel = new Map<string, SpecTemplate>();
  for (const t of templateItems ?? []) {
    if (t.spec_key) byKey.set(t.spec_key, t);
    if (t.label?.trim()) byLabel.set(t.label.trim().toLowerCase(), t);
  }
  return (
    (spec.spec_key ? byKey.get(spec.spec_key) : undefined) ??
    byLabel.get(spec.label.trim().toLowerCase())
  );
};

/**
 * Inserta o actualiza, dentro de `specs`, el valor de un spec YA MATCHEADO
 * a un template (`tmpl`) — por id `spec-{spec_def_id}`, el id legacy
 * `tmpl-{spec_def_id}`, o mismo label (por si quedó con un id viejo). Mismo
 * upsert que EquipoFormDialogV2 duplicaba dos veces.
 */
export const upsertTemplateSpec = (
  specs: Spec[],
  tmpl: SpecTemplate,
  value: string,
  specKey?: string,
): Spec[] => {
  const targetId = `spec-${tmpl.spec_def_id}`;
  const next = [...specs];
  const idx = next.findIndex(
    (x) =>
      x.id === targetId || x.id === `tmpl-${tmpl.spec_def_id}` || sameLabel(x.label, tmpl.label),
  );
  if (idx >= 0) {
    next[idx] = { ...next[idx], value };
  } else {
    next.push({ id: targetId, label: tmpl.label, value, spec_key: specKey });
  }
  return next;
};

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
