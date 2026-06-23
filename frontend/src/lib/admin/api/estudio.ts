import { authedFetch, authedJson, authedPostJson } from "@/lib/authedFetch";
import type {
  EstudioConfig,
  EstudioInput,
  EstudioFoto,
  EstudioSlotFijo,
  EstudioSlotInput,
  EstudioPackEquipoCurado,
  FotoOrdenItem,
  DescuentoJornada,
} from "./types";

// ── Estudio (singleton E1) ───────────────────────────────────────────────────

export const estudioAdminApi = {
  get: () => authedJson<EstudioConfig>("/api/estudio"),
  listPack: () => authedJson<{ pack: EstudioPackEquipoCurado[] }>("/api/admin/estudio/pack"),
  addPackEquipo: (equipo_id: number) =>
    authedPostJson<{ pack: EstudioPackEquipoCurado[] }>("/api/admin/estudio/pack", { equipo_id }),
  removePackEquipo: (equipo_id: number) =>
    authedFetch(`/api/admin/estudio/pack/${equipo_id}`, { method: "DELETE" }).then(async (r) => {
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d?.detail ?? `DELETE pack → ${r.status}`);
      }
      return r.json() as Promise<{ pack: EstudioPackEquipoCurado[] }>;
    }),
  listSlots: () => authedJson<{ slots: EstudioSlotFijo[] }>("/api/admin/estudio/slots"),
  createSlot: (data: EstudioSlotInput) =>
    authedPostJson<EstudioSlotFijo>("/api/admin/estudio/slots", data),
  updateSlot: (id: number, data: Partial<EstudioSlotInput>) =>
    authedFetch(`/api/admin/estudio/slots/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(async (r) => {
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d?.detail ?? `PATCH slot → ${r.status}`);
      }
      return r.json() as Promise<EstudioSlotFijo>;
    }),
  deleteSlot: (id: number) =>
    authedFetch(`/api/admin/estudio/slots/${id}`, { method: "DELETE" }).then(async (r) => {
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d?.detail ?? `DELETE slot → ${r.status}`);
      }
      return r.json() as Promise<{ ok: boolean }>;
    }),
  update: (data: EstudioInput) =>
    authedFetch("/api/admin/estudio", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(async (r) => {
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d?.detail ?? `PATCH estudio → ${r.status}`);
      }
      return r.json() as Promise<EstudioConfig>;
    }),
  deleteFoto: (fotoId: number) =>
    authedFetch(`/api/admin/estudio/fotos/${fotoId}`, { method: "DELETE" }).then(async (r) => {
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d?.detail ?? `DELETE foto → ${r.status}`);
      }
      return r.json() as Promise<{ ok: boolean }>;
    }),
  reorderFotos: (fotos: FotoOrdenItem[]) =>
    authedFetch("/api/admin/estudio/fotos/orden", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fotos }),
    }).then(async (r) => {
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d?.detail ?? `PATCH fotos/orden → ${r.status}`);
      }
      return r.json() as Promise<{ fotos: EstudioFoto[] }>;
    }),
};

// ── Descuentos por jornadas ──────────────────────────────────────────────────

export const descuentosJornadaApi = {
  list: () => authedJson<DescuentoJornada[]>("/api/descuentos-jornada"),
  create: (data: { jornadas: number; pct: number }) =>
    authedPostJson<DescuentoJornada>("/api/admin/descuentos-jornada", data),
  delete: (id: number) => authedFetch(`/api/admin/descuentos-jornada/${id}`, { method: "DELETE" }),
};
