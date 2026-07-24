import type { Sesion, Taller } from "@/lib/api";

/**
 * F5: sintetiza 2 `Sesion` desde `programa_teorica`/`programa_practica`
 * (legacy) para talleres que todavía no tienen clases ricas cargadas —
 * mismo criterio que el backfill de F2 (título "Teórica"/"Práctica",
 * bullets como descripción). `hora_inicio_min/hora_fin_min` quedan en 0
 * (sin sentido numérico): estas sesiones sintéticas son SOLO para
 * `ProgramaSection`, nunca para `TallerCalendario` (que sigue leyendo
 * `taller.sesiones` reales). Se borra en F6 junto con las columnas legacy.
 */
export function clasesDesdeLegacy(taller: Taller): Sesion[] {
  const clases: Sesion[] = [];
  if (taller.programa_teorica.length > 0) {
    clases.push({
      fecha: taller.fecha_inicio,
      hora_inicio_min: 0,
      hora_fin_min: 0,
      hora_inicio_str: taller.horario,
      hora_fin_str: "",
      titulo: "Teórica",
      descripcion: taller.programa_teorica.join("\n"),
      nota: "",
      portada_url: "",
    });
  }
  if (taller.programa_practica.length > 0) {
    clases.push({
      fecha: taller.fecha_fin,
      hora_inicio_min: 0,
      hora_fin_min: 0,
      hora_inicio_str: taller.horario,
      hora_fin_str: "",
      titulo: "Práctica",
      descripcion: taller.programa_practica.join("\n"),
      nota: "",
      portada_url: "",
    });
  }
  return clases;
}

/** Clases a mostrar en `ProgramaSection`: reales si hay, legacy si no. */
export function clasesParaPrograma(taller: Taller): Sesion[] {
  return taller.sesiones.length > 0 ? taller.sesiones : clasesDesdeLegacy(taller);
}
