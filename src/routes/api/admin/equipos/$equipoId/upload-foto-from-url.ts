import { createFileRoute } from "@tanstack/react-router";

import { ADMIN_EMAILS } from "@/lib/admin-emails";
import { supabaseAdmin } from "@/integrations/supabase/client.server";

const BUCKET = "equipos-fotos";

type DownloadedImage = {
  bytes: ArrayBuffer;
  contentType: string;
};

export const Route = createFileRoute("/api/admin/equipos/$equipoId/upload-foto-from-url")({
  server: {
    handlers: {
      POST: async ({ request, params }: { request: Request; params: { equipoId: string } }) => {
        const admin = await requireAdmin(request);
        if (!admin.ok) return jsonError(admin.status, admin.detail);

        const equipoId = Number(params.equipoId);
        if (!Number.isFinite(equipoId) || equipoId <= 0) {
          return jsonError(400, "ID de equipo inválido");
        }

        const payload = await request.json().catch(() => null) as { url?: unknown } | null;
        const url = typeof payload?.url === "string" ? payload.url.trim() : "";
        if (!url) return jsonError(400, "URL vacía");
        if (!url.toLowerCase().startsWith("http://") && !url.toLowerCase().startsWith("https://")) {
          return jsonError(400, "URL inválida");
        }

        if (url.includes(`/storage/v1/object/public/${BUCKET}/`)) {
          return Response.json({ public_url: url, path: null, skipped: true });
        }

        let image: DownloadedImage;
        try {
          image = await downloadImage(url);
        } catch (error) {
          return jsonError(502, error instanceof Error ? error.message : "No se pudo descargar la imagen");
        }

        const ext = extFromContentType(image.contentType);
        const path = `equipos/${equipoId}/foto-${Date.now()}.${ext}`;
        const { error } = await supabaseAdmin.storage
          .from(BUCKET)
          .upload(path, image.bytes, {
            contentType: image.contentType,
            upsert: false,
            cacheControl: "3600",
          });

        if (error) return jsonError(502, `Storage devolvió error: ${error.message}`);

        const { data } = supabaseAdmin.storage.from(BUCKET).getPublicUrl(path);
        return Response.json({
          public_url: data.publicUrl,
          path,
          size: image.bytes.byteLength,
          content_type: image.contentType,
        });
      },
    },
  },
} as any);

async function requireAdmin(request: Request): Promise<{ ok: true } | { ok: false; status: number; detail: string }> {
  const auth = request.headers.get("authorization") ?? "";
  const token = auth.match(/^Bearer\s+(.+)$/i)?.[1];
  if (!token) return { ok: false, status: 401, detail: "Iniciá sesión como admin para subir fotos." };

  const { data, error } = await supabaseAdmin.auth.getUser(token);
  if (error || !data.user?.email) {
    return { ok: false, status: 401, detail: "Sesión inválida o expirada. Volvé a iniciar sesión." };
  }

  const email = data.user.email.toLowerCase();
  const allowed = ADMIN_EMAILS.map((item) => item.toLowerCase()).includes(email);
  if (!allowed) return { ok: false, status: 403, detail: "Tu cuenta no tiene permisos de administración." };

  return { ok: true };
}

async function downloadImage(url: string): Promise<DownloadedImage> {
  const parsed = new URL(url);
  const primaryReferer = refererForHost(parsed.hostname);
  const attempts = [
    { target: url, referer: primaryReferer },
    { target: url, referer: null },
    { target: url, referer: "https://www.google.com/" },
    { target: weservUrl(url), referer: null },
  ];

  let lastStatus = 0;
  let lastText = "";

  for (const attempt of attempts) {
    const response = await fetch(attempt.target, {
      headers: imageHeaders(attempt.referer),
      redirect: "follow",
      signal: AbortSignal.timeout(20_000),
    });
    lastStatus = response.status;
    const contentType = response.headers.get("content-type") ?? "image/jpeg";

    if (response.ok && contentType.startsWith("image/")) {
      const bytes = await response.arrayBuffer();
      if (bytes.byteLength < 1024) throw new Error(`Imagen muy chica (${bytes.byteLength} bytes)`);
      return { bytes, contentType };
    }

    if (!shouldTryNext(response.status)) {
      lastText = (await response.text().catch(() => "")).slice(0, 200);
      break;
    }
    lastText = (await response.text().catch(() => "")).slice(0, 200);
  }

  throw new Error(`Origen devolvió ${lastStatus} para host ${parsed.hostname}. ${lastText}`.trim());
}

function imageHeaders(referer: string | null): HeadersInit {
  const headers: Record<string, string> = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    Accept: "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
    "Cache-Control": "no-cache",
  };
  if (referer) headers.Referer = referer;
  return headers;
}

function refererForHost(hostname: string): string {
  const host = hostname.toLowerCase();
  if (host.endsWith("bhphotovideo.com")) return "https://www.bhphotovideo.com/";
  if (host.endsWith("adorama.com")) return "https://www.adorama.com/";
  return `https://${host}/`;
}

function weservUrl(url: string): string {
  const stripped = url.includes("://") ? url.split("://", 2)[1] : url;
  return `https://images.weserv.nl/?url=${encodeURIComponent(stripped)}`;
}

function shouldTryNext(status: number): boolean {
  return [401, 403, 404, 429].includes(status) || status >= 500;
}

function extFromContentType(contentType: string): string {
  const value = contentType.toLowerCase();
  if (value.includes("png")) return "png";
  if (value.includes("webp")) return "webp";
  if (value.includes("avif")) return "avif";
  if (value.includes("gif")) return "gif";
  return "jpg";
}

function jsonError(status: number, detail: string): Response {
  return Response.json({ detail }, { status });
}