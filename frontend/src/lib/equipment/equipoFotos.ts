/**
 * Helpers para la galería multi-foto de equipos (F2).
 *
 * Endpoints admin del backend:
 *   GET    /api/admin/equipos/{id}/fotos
 *   POST   /api/admin/equipos/{id}/fotos              (multipart/form-data)
 *   POST   /api/admin/equipos/{id}/fotos/from-url     (JSON {url})
 *   DELETE /api/admin/equipos/{id}/fotos/{foto_id}
 *   PATCH  /api/admin/equipos/{id}/fotos/orden        (JSON {fotos: [...]})
 */

import { authedFetch } from "@/lib/authedFetch";

export type EquipoFoto = {
  id: number;
  url: string;
  path: string | null;
  media_id: number | null;
  orden: number;
  es_principal: boolean;
  created_at: string | null;
};

export type EquipoFotoOrdenItem = {
  id: number;
  orden: number;
  es_principal: boolean;
};

export async function getEquipoFotos(equipoId: number): Promise<EquipoFoto[]> {
  const res = await authedFetch(`/api/admin/equipos/${equipoId}/fotos`);
  if (!res.ok) throw new Error(`get-fotos → ${res.status}`);
  const data = (await res.json()) as { fotos: EquipoFoto[] };
  return data.fotos;
}

export async function uploadEquipoFoto(equipoId: number, file: File): Promise<EquipoFoto> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await authedFetch(`/api/admin/equipos/${equipoId}/fotos`, {
    method: "POST",
    body: fd,
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(detail.detail ?? `upload-foto → ${res.status}`);
  }
  return res.json() as Promise<EquipoFoto>;
}

export async function uploadEquipoFotoFromUrl(equipoId: number, url: string): Promise<EquipoFoto> {
  const res = await authedFetch(`/api/admin/equipos/${equipoId}/fotos/from-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(detail.detail ?? `upload-foto-from-url → ${res.status}`);
  }
  return res.json() as Promise<EquipoFoto>;
}

export async function deleteEquipoFoto(equipoId: number, fotoId: number): Promise<void> {
  const res = await authedFetch(`/api/admin/equipos/${equipoId}/fotos/${fotoId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(detail.detail ?? `delete-foto → ${res.status}`);
  }
}

export async function reorderEquipoFotos(
  equipoId: number,
  items: EquipoFotoOrdenItem[],
): Promise<{ fotos: EquipoFoto[] }> {
  const res = await authedFetch(`/api/admin/equipos/${equipoId}/fotos/orden`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fotos: items }),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(detail.detail ?? `reorder-fotos → ${res.status}`);
  }
  return res.json() as Promise<{ fotos: EquipoFoto[] }>;
}
