/**
 * Helpers para fotos de equipo.
 *
 * Las fotos se almacenan en Cloudflare R2 vía endpoints admin del backend:
 *   - POST /api/admin/equipos/{id}/upload-foto         (multipart/form-data)
 *   - POST /api/admin/equipos/{id}/upload-foto-from-url (JSON {url})
 *
 * El backend optimiza con Pillow (resize a 1600px max + WebP q=85) y
 * sube a R2 con Cache-Control inmutable. Devuelve la public_url del CDN.
 */

import { authedFetch } from "@/lib/authedFetch";

type UploadResponse = {
  public_url: string;
  path: string | null;
  size?: number;
  size_original?: number;
  content_type?: string;
  width?: number | null;
  height?: number | null;
  skipped?: boolean;
};

/** ¿La URL ya está hospedada en nuestro storage? Detecta R2 (pub-*.r2.dev) o
 *  custom domain. Soporta el esquema nuevo ({id}_{slug}/{id}_{slug}.ext) y
 *  el viejo (equipos/{id}/...) para compatibilidad durante la migración.
 */
export function isHostedUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  return (
    /\/equipos\/\d+\/[^/]+\.(webp|jpg|jpeg|png|avif|gif)/i.test(url) ||
    /\/\d+_[a-z0-9-]+\/[^/]+\.(webp|jpg|jpeg|png|avif|gif)/i.test(url)
  );
}

/** Backwards compat: alias del antiguo isBucketUrl. */
export const isBucketUrl = isHostedUrl;

/** Sube un File del browser al backend. Devuelve la URL pública. */
export async function uploadFileToBucket(equipoId: number | string, file: File): Promise<string> {
  const fd = new FormData();
  fd.append("file", file);

  const res = await authedFetch(`/api/admin/equipos/${equipoId}/upload-foto`, {
    method: "POST",
    body: fd,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail ?? `upload-foto → ${res.status}`);
  }
  const data = (await res.json()) as UploadResponse;
  return data.public_url;
}

/** Descarga una URL externa vía backend, optimiza y la sube a R2.
 *  Si la URL ya pertenece a nuestro storage, la devuelve sin tocarla.
 */
export async function uploadExternalUrlToBucket(
  equipoId: number | string,
  externalUrl: string,
): Promise<string> {
  if (!externalUrl) throw new Error("URL vacía");
  if (isHostedUrl(externalUrl)) return externalUrl;

  const res = await authedFetch(`/api/admin/equipos/${equipoId}/upload-foto-from-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: externalUrl }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail ?? `upload-foto-from-url → ${res.status}`);
  }
  const data = (await res.json()) as UploadResponse;
  return data.public_url;
}
