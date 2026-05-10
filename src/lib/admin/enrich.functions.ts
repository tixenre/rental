import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";

const Input = z.object({
  nombre: z.string().min(1),
  marca: z.string().optional().nullable(),
  modelo: z.string().optional().nullable(),
});

export type EnriquecerResult = {
  marca: string | null;
  modelo: string | null;
  nombre_normalizado: string;
  descripcion: string;
  specs: { label: string; value: string }[];
  foto_url: string | null;
  fuente_url: string;
  fuente_titulo: string;
};

function adminEmails(): string[] {
  const raw = process.env.ADMIN_EMAILS ?? "tinchosantini@gmail.com";
  return raw.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
}

export const enriquecerEquipoFn = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((data: unknown) => Input.parse(data))
  .handler(async ({ data, context }): Promise<EnriquecerResult> => {
    const email = String(
      (context.claims as Record<string, unknown>).email ?? "",
    ).toLowerCase();
    if (!email || !adminEmails().includes(email)) {
      throw new Response("Forbidden: admin only", { status: 403 });
    }

    const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY;
    const LOVABLE_API_KEY = process.env.LOVABLE_API_KEY;
    if (!FIRECRAWL_API_KEY) throw new Error("FIRECRAWL_API_KEY no configurado");
    if (!LOVABLE_API_KEY) throw new Error("LOVABLE_API_KEY no configurado");

    const query = [data.marca, data.nombre, data.modelo]
      .filter(Boolean)
      .join(" ")
      .trim();

    // 1. Firecrawl search — preferimos B&H, fallback Adorama, luego web
    const searchRes = await fetch("https://api.firecrawl.dev/v2/search", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${FIRECRAWL_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: `${query} site:bhphotovideo.com OR site:adorama.com`,
        limit: 3,
      }),
    });
    if (!searchRes.ok) {
      const body = await searchRes.text();
      throw new Error(`Firecrawl search ${searchRes.status}: ${body.slice(0, 200)}`);
    }
    const searchData = (await searchRes.json()) as {
      data?: { web?: Array<{ url: string; title?: string }> } | Array<{ url: string; title?: string }>;
    };
    const rawResults = Array.isArray(searchData?.data)
      ? (searchData.data as Array<{ url: string; title?: string }>)
      : (searchData?.data?.web ?? []);

    // Si no hay nada en B&H/Adorama, búsqueda libre
    let results = rawResults;
    if (results.length === 0) {
      const fallbackRes = await fetch("https://api.firecrawl.dev/v2/search", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${FIRECRAWL_API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query, limit: 3 }),
      });
      if (fallbackRes.ok) {
        const fb = (await fallbackRes.json()) as {
          data?: { web?: Array<{ url: string; title?: string }> } | Array<{ url: string; title?: string }>;
        };
        results = Array.isArray(fb?.data)
          ? (fb.data as Array<{ url: string; title?: string }>)
          : (fb?.data?.web ?? []);
      }
    }

    const top = results[0];
    if (!top?.url) throw new Error("No se encontraron resultados en internet.");

    // 2. Firecrawl scrape
    const scrapeRes = await fetch("https://api.firecrawl.dev/v2/scrape", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${FIRECRAWL_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        url: top.url,
        formats: ["markdown"],
        onlyMainContent: true,
      }),
    });
    if (!scrapeRes.ok) {
      const body = await scrapeRes.text();
      throw new Error(`Firecrawl scrape ${scrapeRes.status}: ${body.slice(0, 200)}`);
    }
    const scrapeJson = (await scrapeRes.json()) as {
      data?: { markdown?: string; metadata?: Record<string, unknown> };
      markdown?: string;
      metadata?: Record<string, unknown>;
    };
    const markdown = scrapeJson?.data?.markdown ?? scrapeJson?.markdown ?? "";
    const meta = (scrapeJson?.data?.metadata ?? scrapeJson?.metadata ?? {}) as Record<string, unknown>;

    if (!markdown || markdown.length < 100) {
      throw new Error("La página no devolvió contenido útil para extraer.");
    }

    // 3. Lovable AI extracción estructurada (tool calling)
    const aiRes = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash",
        messages: [
          {
            role: "system",
            content:
              "Extraés información de equipos audiovisuales (cámaras, lentes, luces, audio, etc.) desde páginas de B&H, Adorama u otros e-commerces. Usá SIEMPRE la herramienta extract_equipo. Specs: máximo 8, label corto (ej: 'Sensor', 'Apertura'), value conciso. Descripcion: 1-2 oraciones en español. Si la foto_url no es absoluta o no se ve confiable, dejala vacía.",
          },
          {
            role: "user",
            content: `URL: ${top.url}\nBúsqueda: ${query}\n\nContenido scrapeado:\n${markdown.slice(0, 12000)}`,
          },
        ],
        tools: [
          {
            type: "function",
            function: {
              name: "extract_equipo",
              description: "Extrae datos del equipo desde el contenido scrapeado",
              parameters: {
                type: "object",
                properties: {
                  marca: { type: "string" },
                  modelo: { type: "string" },
                  nombre_normalizado: {
                    type: "string",
                    description: "Nombre limpio del producto, sin la marca al inicio",
                  },
                  descripcion: { type: "string" },
                  specs: {
                    type: "array",
                    items: {
                      type: "object",
                      properties: {
                        label: { type: "string" },
                        value: { type: "string" },
                      },
                      required: ["label", "value"],
                      additionalProperties: false,
                    },
                  },
                  foto_url: {
                    type: "string",
                    description: "URL absoluta (https://...) de la imagen principal del producto",
                  },
                },
                required: ["marca", "modelo", "descripcion", "specs"],
                additionalProperties: false,
              },
            },
          },
        ],
        tool_choice: { type: "function", function: { name: "extract_equipo" } },
      }),
    });

    if (!aiRes.ok) {
      if (aiRes.status === 429) throw new Error("Rate-limit de Lovable AI. Probá en un minuto.");
      if (aiRes.status === 402) throw new Error("Sin créditos de Lovable AI. Recargá en Settings → Workspace → Usage.");
      const body = await aiRes.text();
      throw new Error(`Lovable AI ${aiRes.status}: ${body.slice(0, 200)}`);
    }

    const aiData = (await aiRes.json()) as {
      choices?: Array<{
        message?: {
          tool_calls?: Array<{ function?: { arguments?: string } }>;
        };
      }>;
    };
    const argsStr = aiData?.choices?.[0]?.message?.tool_calls?.[0]?.function?.arguments;
    if (!argsStr) throw new Error("La IA no devolvió extracción estructurada.");

    let extracted: {
      marca?: string;
      modelo?: string;
      nombre_normalizado?: string;
      descripcion?: string;
      specs?: Array<{ label: string; value: string }>;
      foto_url?: string;
    };
    try {
      extracted = JSON.parse(argsStr);
    } catch {
      throw new Error("La IA devolvió JSON inválido.");
    }

    const ogImage =
      (meta.ogImage as string | undefined) ??
      (meta["og:image"] as string | undefined) ??
      null;

    const fotoUrl = (() => {
      const candidate = extracted.foto_url || ogImage;
      if (!candidate) return null;
      if (!/^https?:\/\//i.test(candidate)) return ogImage || null;
      return candidate;
    })();

    return {
      marca: extracted.marca?.trim() || data.marca || null,
      modelo: extracted.modelo?.trim() || data.modelo || null,
      nombre_normalizado: (extracted.nombre_normalizado || data.nombre).trim(),
      descripcion: (extracted.descripcion || "").trim(),
      specs: Array.isArray(extracted.specs) ? extracted.specs.slice(0, 12) : [],
      foto_url: fotoUrl,
      fuente_url: top.url,
      fuente_titulo: top.title || (meta.title as string | undefined) || top.url,
    };
  });
