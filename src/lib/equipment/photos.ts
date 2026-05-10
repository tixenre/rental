/**
 * Helpers para fotos de equipo.
 *
 * Las fotos viven en el bucket `equipos-fotos` bajo `equipos/{equipoId}/foto-{ts}.{ext}`,
 * de modo que la imagen quede atada al equipo y no a una URL externa
 * (B&H/Adorama bloquean hotlinking).
 */

import { supabase } from "@/integrations/supabase/client";
import { authedFetch } from "@/lib/authedFetch";

const BUCKET = "equipos-fotos";

export function isBucketUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  return url.includes(`/storage/v1/object/public/${BUCKET}/`);
}

function extFromContentType(ct: string | null): string {
  if (!ct) return "jpg";
  if (ct.includes("png")) return "png";
  if (ct.includes("webp")) return "webp";
  if (ct.includes("avif")) return "avif";
  if (ct.includes("gif")) return "gif";
  return "jpg";
}

async function uploadBlob(equipoId: number | string, blob: Blob, ext: string): Promise<string> {
  const path = `equipos/${equipoId}/foto-${Date.now()}.${ext}`;
  const { error } = await supabase.storage
    .from(BUCKET)
    .upload(path, blob, { contentType: blob.type || `image/${ext}`, upsert: false });
  if (error) throw error;
  const { data } = supabase.storage.from(BUCKET).getPublicUrl(path);
  return data.publicUrl;
}

export async function uploadFileToBucket(
  equipoId: number | string,
  file: File,
): Promise<string> {
  const ext = (file.name.split(".").pop() || "jpg").toLowerCase();
  return uploadBlob(equipoId, file, ext);
}

/**
 * Descarga una URL externa vía el proxy admin del backend (evita CORS/hotlinking)
 * y la sube al bucket. Devuelve la URL pública del bucket.
 *
 * Si la URL ya pertenece al bucket, la devuelve sin tocarla.
 */
export async function uploadExternalUrlToBucket(
  equipoId: number | string,
  externalUrl: string,
): Promise<string> {
  if (!externalUrl) throw new Error("URL vacía");
  if (isBucketUrl(externalUrl)) return externalUrl;

  const res = await authedFetch(
    `/api/admin/proxy-image?url=${encodeURIComponent(externalUrl)}`,
  );
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail ?? `proxy-image → ${res.status}`);
  }
  const blob = await res.blob();
  const ext = extFromContentType(blob.type);
  return uploadBlob(equipoId, blob, ext);
}
