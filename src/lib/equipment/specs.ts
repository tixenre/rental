/**
 * Selección de "specs destacadas" por categoría.
 *
 * La idea: ante una lista de specs (label/value) que vino del enriquecedor,
 * elegir las 3-4 más representativas según el tipo de equipo, y devolver
 * el resto separado para mostrar en un acordeón "ver todas".
 *
 * Match heurístico por substring sobre el label (lowercase, sin acentos).
 */

import type { Category } from "@/data/equipment";

export type Spec = { label: string; value: string };

const norm = (s: string) =>
  s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();

// Keywords ordenadas por importancia, max 4 destacadas
const PRIORITY_BY_CATEGORY: Partial<Record<Category, string[]>> = {
  Cámaras:   ["sensor", "resolucion", "video", "iso", "montura", "formato", "frame", "fps"],
  Lentes:    ["focal", "apertura", "diafragma", "montura", "estabilizacion", "minima"],
  Luces:     ["potencia", "watt", "lumen", "temperatura", "color", "cri", "tlci", "alimentacion", "bateria"],
  Tungsteno: ["potencia", "watt", "temperatura", "alimentacion"],
  Modificadores: ["tipo", "tamaño", "tamano", "difusion", "montura"],
  Sonido:    ["tipo", "patron", "polar", "conexion", "frecuencia", "alcance", "bateria"],
  Audio:     ["tipo", "patron", "polar", "conexion", "frecuencia"],
  Monitores: ["tamaño", "tamano", "resolucion", "brillo", "nits", "panel", "entradas"],
  Trípode:   ["altura", "carga", "peso", "cabezal", "patas"],
  Soportes:  ["altura", "carga", "peso"],
  Baterías:  ["capacidad", "voltaje", "salida", "wh", "tipo"],
  Filtros:   ["tipo", "diametro", "stops", "densidad"],
};

const DEFAULT_PRIORITY = ["sensor", "resolucion", "potencia", "montura", "tipo"];

export function pickHighlightSpecs(
  category: Category | undefined,
  specs: Spec[],
  max = 4,
): { highlights: Spec[]; rest: Spec[] } {
  if (!specs || specs.length === 0) return { highlights: [], rest: [] };

  const priority = (category && PRIORITY_BY_CATEGORY[category]) || DEFAULT_PRIORITY;
  const used = new Set<number>();
  const highlights: Spec[] = [];

  for (const kw of priority) {
    if (highlights.length >= max) break;
    const idx = specs.findIndex(
      (s, i) => !used.has(i) && norm(s.label).includes(kw),
    );
    if (idx !== -1) {
      used.add(idx);
      highlights.push(specs[idx]);
    }
  }

  // Rellenar con las primeras specs no usadas hasta llegar a `max`
  for (let i = 0; i < specs.length && highlights.length < max; i++) {
    if (used.has(i)) continue;
    used.add(i);
    highlights.push(specs[i]);
  }

  const rest = specs.filter((_, i) => !used.has(i));
  return { highlights, rest };
}
