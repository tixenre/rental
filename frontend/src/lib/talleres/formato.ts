// ── Formato de horarios de talleres (minutos desde medianoche) ─────────────────
// Escuela v2 F1: las clases guardan horas en MINUTOS (510 = 8:30). El backend
// resuelve los strings de display (`hora_inicio_str`); este helper existe SOLO
// para estado local todavía no guardado (el asistente de clases del admin) —
// no reimplementar el formato en componentes.

/** 510 → "08:30", 780 → "13:00", 1440 → "24:00". */
export function fmtHhmm(minutos: number): string {
  const h = Math.floor(minutos / 60);
  const m = minutos % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}
