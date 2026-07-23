import { authedFetch, authedJson, authedPostJson } from "@/lib/authedFetch";
import type {
  ClaseBody,
  EdicionAdmin,
  EdicionKpis,
  TallerConcepto,
  Inscripcion,
  Instructor,
  Interesado,
  Trabajo,
} from "./types";

async function _ok<T>(r: Response): Promise<T> {
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error((d as { detail?: string }).detail ?? `Error ${r.status}`);
  }
  return r.json() as Promise<T>;
}

export const talleresAdminApi = {
  list: () => authedJson<TallerConcepto[]>("/api/admin/talleres"),

  createConcepto: (body: object) => authedPostJson<TallerConcepto>("/api/admin/talleres", body),

  updateConcepto: (conceptoId: number, body: object) =>
    authedJson<TallerConcepto>(`/api/admin/talleres/${conceptoId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  uploadFotoInstructor: (conceptoId: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return authedFetch(`/api/admin/talleres/${conceptoId}/upload-foto-instructor`, {
      method: "POST",
      body: fd,
    }).then((r) => _ok<{ instructor_foto_url?: string }>(r));
  },

  createEdicion: (conceptoId: number, body: object) =>
    authedPostJson<EdicionAdmin>(`/api/admin/talleres/${conceptoId}/ediciones`, body),

  updateEdicion: (edicionId: number, body: object) =>
    authedJson<EdicionAdmin>(`/api/admin/ediciones/${edicionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  updateEdicionClases: (edicionId: number, body: { tipo_taller: string; clases: ClaseBody[] }) =>
    authedJson<EdicionAdmin>(`/api/admin/ediciones/${edicionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  deleteEdicion: (edicionId: number) =>
    authedJson<{ ok: boolean }>(`/api/admin/ediciones/${edicionId}`, { method: "DELETE" }),

  // F2: portada de una clase (solo clases guardadas — necesitan id).
  uploadPortadaClase: (claseId: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return authedFetch(`/api/admin/clases/${claseId}/portada`, {
      method: "POST",
      body: fd,
    }).then((r) => _ok<{ ok: boolean; url: string; media_id: number }>(r));
  },

  deletePortadaClase: (claseId: number) =>
    authedJson<{ ok: boolean }>(`/api/admin/clases/${claseId}/portada`, { method: "DELETE" }),

  listInscripciones: (edicionId: number) =>
    authedJson<Inscripcion[]>(`/api/admin/ediciones/${edicionId}/inscripciones`),

  // F4c: mini-KPIs de una edición (señas + plata, ya resuelta por el backend).
  getEdicionKpis: (edicionId: number) =>
    authedJson<EdicionKpis>(`/api/admin/ediciones/${edicionId}/kpis`),

  eliminarInscripcion: (conceptoId: number, inscripcionId: number) =>
    authedJson<{ ok: boolean }>(
      `/api/admin/talleres/${conceptoId}/inscripciones/${inscripcionId}`,
      { method: "DELETE" },
    ),

  confirmarInscripcion: (conceptoId: number, inscripcionId: number) =>
    authedJson<{ ok: boolean }>(
      `/api/admin/talleres/${conceptoId}/inscripciones/${inscripcionId}/confirmar`,
      { method: "POST" },
    ),

  // F4b: seña + ofrecer cupo al siguiente.
  verificarSena: (conceptoId: number, inscripcionId: number) =>
    authedJson<{ ok: boolean }>(
      `/api/admin/talleres/${conceptoId}/inscripciones/${inscripcionId}/verificar-sena`,
      { method: "POST" },
    ),

  ofrecerCupo: (conceptoId: number, inscripcionId: number) =>
    authedJson<{ ok: boolean }>(
      `/api/admin/talleres/${conceptoId}/inscripciones/${inscripcionId}/ofrecer-cupo`,
      { method: "POST" },
    ),

  listInteresados: (conceptoId: number) =>
    authedJson<Interesado[]>(`/api/admin/talleres/${conceptoId}/interesados`),

  notificarInteresado: (conceptoId: number, interesadoId: number) =>
    authedJson<{ ok: boolean }>(
      `/api/admin/talleres/${conceptoId}/interesados/${interesadoId}/notificar`,
      { method: "POST" },
    ),

  notificarCambios: (conceptoId: number, mensaje: string) =>
    authedJson<{ enviados: number; fallidos: number }>(
      `/api/admin/talleres/${conceptoId}/notificar-cambios`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensaje: mensaje || undefined }),
      },
    ),

  /** Devuelve el Response crudo — el consumidor arma el blob/URL de descarga. */
  exportInscripcionesCsv: (conceptoId: number) =>
    authedFetch(`/api/admin/talleres/${conceptoId}/inscripciones/export-csv`),

  // F3: instructores como entidad (mini-CRUD) + link N↔N con el taller.
  listInstructores: () => authedJson<Instructor[]>("/api/admin/instructores"),

  createInstructor: (body: {
    nombre: string;
    rol?: string;
    descripcion?: string;
    instagram?: string;
    web?: string;
  }) => authedPostJson<Instructor>("/api/admin/instructores", body),

  updateInstructor: (instructorId: number, body: object) =>
    authedJson<Instructor>(`/api/admin/instructores/${instructorId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  deleteInstructor: (instructorId: number) =>
    authedJson<{ ok: boolean }>(`/api/admin/instructores/${instructorId}`, { method: "DELETE" }),

  uploadFotoInstructorPerfil: (instructorId: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return authedFetch(`/api/admin/instructores/${instructorId}/upload-foto`, {
      method: "POST",
      body: fd,
    }).then((r) => _ok<{ ok: boolean; url: string; media_id: number }>(r));
  },

  setTallerInstructores: (conceptoId: number, instructorIds: number[]) =>
    authedJson<{ instructores: Instructor[] }>(`/api/admin/talleres/${conceptoId}/instructores`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instructor_ids: instructorIds }),
    }),

  // F4c: trabajos pasados (solo YouTube, sin testimonios).
  crearTrabajo: (conceptoId: number, body: { titulo?: string; youtube_url: string }) =>
    authedPostJson<Trabajo>(`/api/admin/talleres/${conceptoId}/trabajos`, body),

  editarTrabajo: (
    trabajoId: number,
    body: { titulo?: string; youtube_url?: string; orden?: number },
  ) =>
    authedJson<Trabajo>(`/api/admin/trabajos/${trabajoId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  eliminarTrabajo: (trabajoId: number) =>
    authedJson<{ ok: boolean }>(`/api/admin/trabajos/${trabajoId}`, { method: "DELETE" }),
};
