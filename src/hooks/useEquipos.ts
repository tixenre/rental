import { useQuery } from "@tanstack/react-query";
import { apiGetEquipos, apiGetCategorias, apiGetDisponibilidad, type BackendEquipo } from "@/lib/api";
import { type Equipment, type Category, equipment as MOCK_EQUIPMENT } from "@/data/equipment";
import { format } from "date-fns";

/* ─── Inferencia de categoría desde nombre/marca/etiquetas ────────────── */
//
// El backend guarda las etiquetas vacías para la mayoría de los equipos,
// así que inferimos la categoría a partir del nombre y la marca del equipo.
// Las reglas se evalúan en orden: la primera que matchea gana.

type Rule = { keywords: string[]; category: Category };

// Orden importa: más específico primero
const RULES: Rule[] = [
  // Baterías (antes de genéricos como "canon", "sony")
  { keywords: ["batería", "bateria", "battery", "v-mount", "vmount", "np-f", "lp-e", "np-fz", "kit baterías", "kit bateria"], category: "Baterías" },

  // Filtros
  { keywords: ["filtro", "filter", "polarizador", "difusión", "pro-mist", "tiffen"], category: "Filtros" },

  // Cámaras (antes de lentes para que "Canon" no matchee lentes)
  { keywords: ["cámara", "camara", "camera", "gopro", "insta360", "komodo", "fx3", "zv-e1", "a7 v", "c200", "cinema line"], category: "Cámaras" },

  // Lentes
  { keywords: ["lente", "lens", "lentes", "kit lentes", "laowa", "tokina", "zeiss", "speedbooster", "montura"], category: "Lentes" },

  // Monitores
  { keywords: ["monitor", "video assist", "smallhd", "lilliput", "viltrox", "atomos"], category: "Monitores" },

  // Comunicación
  { keywords: ["intercom", "solidcom", "hollyland"], category: "Comunicación" },

  // Flash
  { keywords: ["flash"], category: "Flash" },

  // Sonido (antes de "wireless" genérico)
  { keywords: ["micrófono", "microfono", "microphone", "lavalier", "shotgun", "wireless go", "dji mic", "rodecaster", "caña boom", "boom arm", "sennheiser", "zeppelin", "inalámbrico rode"], category: "Sonido" },

  // Brazo Mágico
  { keywords: ["brazo mágico", "brazo magico", "brazo articulado", "brazo avenger", "brazo con rótula", "magic arm", "superflex"], category: "Brazo Mágico" },

  // Stands
  { keywords: ["c-stand", "stand", "backdrop"], category: "Stands" },

  // Tungsteno (antes de "luz" genérico)
  { keywords: ["tungsteno", "fresnel tungsteno", "par mil", "mole richardson", "fresnel arri", "lowel"], category: "Tungsteno" },

  // Modificadores de luz
  { keywords: ["softbox", "bandera negra", "frame difusión", "frame difusion", "reflector", "fresnel attachment", "globo china", "lantern", "modificador"], category: "Modificadores" },

  // Luces (genérico, después de Tungsteno y Modificadores)
  { keywords: ["luz ", "luz led", "luz on-camera", "luz open face", "spotlight", "fresnel", "kino flo", "nanlite", "amaran", "aputure", "godox vl", "godox tl", "godox m1", "arri", "dracast", "yongnuo", "pampa tubo", "máquina de humo", "maquina de humo"], category: "Luces" },

  // Trípode / movimiento
  { keywords: ["trípode", "tripode", "tripod", "manfrotto", "sachtler", "slider", "riel dolly", "dolly", "steadicam", "gimbal", "ronin", "glidecam", "follow focus", "nucleus"], category: "Trípode" },

  // Grips
  { keywords: ["clamp", "car mount", "jaw clamp", "junior pin", "baby pin", "wall plate", "pinza", "sopapa", "matebox", "matte box"], category: "Grips" },
];

function inferCategory(nombre: string, marca: string): Category {
  const text = `${nombre} ${marca}`.toLowerCase();

  for (const rule of RULES) {
    for (const kw of rule.keywords) {
      if (text.includes(kw)) return rule.category;
    }
  }

  return "Accesorios";
}

function resolveCategory(etiquetas: string[], nombre: string, marca: string): Category {
  // 1. Si hay etiquetas explícitas, intentar mapearlas
  for (const tag of etiquetas) {
    const t = tag.toLowerCase().trim();
    for (const rule of RULES) {
      for (const kw of rule.keywords) {
        if (t.includes(kw)) return rule.category;
      }
    }
  }
  // 2. Inferir desde nombre y marca
  return inferCategory(nombre, marca);
}

/* ─── Nombre público derivado ──────────────────────────────────────── */
//
// Combina tipo (primera categoría asignada) + marca + modelo + montura +
// formato + resolución (de la ficha técnica). Si no hay ficha ni categorías,
// cae al combo viejo "nombre + modelo".

function buildPublicName(e: BackendEquipo): string {
  const tipo = e.categorias?.[0]?.nombre?.trim() ?? "";
  const marca = (e.marca ?? "").trim();
  const modelo = (e.modelo ?? "").trim();
  const f = e.ficha;
  const montura = (f?.montura ?? "").trim();
  const formato = (f?.formato ?? "").trim();
  const resolucion = (f?.resolucion ?? "").trim();

  const parts = [tipo, marca, modelo, montura, formato, resolucion]
    .map((s) => s.replace(/\s+/g, " ").trim())
    .filter(Boolean);

  if (parts.length === 0) {
    return e.nombre || "Sin nombre";
  }
  // Dedupe trivial (si el modelo ya está en el nombre / etc.)
  const seen = new Set<string>();
  const out: string[] = [];
  for (const p of parts) {
    const key = p.toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      out.push(p);
    }
  }
  return out.join(" ");
}

/* ─── Adaptador backend → tipo frontend ─────────────────────────────── */

export function backendToEquipment(e: BackendEquipo): Equipment {
  const nombre = e.nombre ?? "";
  const marca  = e.marca  ?? "";
  const publicName = buildPublicName(e);
  const fallbackName = [nombre, e.modelo].filter(Boolean).join(" ") || "Sin nombre";
  const name = publicName || fallbackName;

  const ficha = e.ficha;
  let parsedSpecs: { label: string; value: string }[] = [];
  if (ficha?.specs_json) {
    try {
      const arr = JSON.parse(ficha.specs_json);
      if (Array.isArray(arr)) {
        parsedSpecs = arr
          .filter((s) => s && typeof s === "object" && s.label && s.value)
          .map((s: { label: string; value: string }) => ({ label: String(s.label), value: String(s.value) }));
      }
    } catch {
      /* ignore malformed specs */
    }
  }

  const kit = Array.isArray(e.kit) ? e.kit as Array<{ componente_id: number; nombre: string; cantidad: number }> : [];
  const includes = kit.map((k) => ({
    id: String(k.componente_id),
    name: k.nombre,
    qty: k.cantidad,
  }));

  return {
    id: String(e.id),
    slug: `${marca}-${nombre}`
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || `equipo-${e.id}`,
    name,
    brand: marca || "—",
    category: resolveCategory(e.etiquetas ?? [], nombre, marca),
    pricePerDay: e.precio_jornada ?? 0,
    fotoUrl: e.foto_url ?? null,
    cantidad: e.cantidad ?? 1,
    description: ficha?.descripcion ?? "",
    specs: parsedSpecs,
    isNew: false,
    isCombo: includes.length > 0,
    includes,
    _backendId: e.id,
  };
}

/* ─── Hooks ─────────────────────────────────────────────────────────── */

type EquiposQueryResult = { items: Equipment[]; usingFallback: boolean };

export function useEquipos() {
  const q = useQuery<EquiposQueryResult>({
    queryKey: ["equipos"],
    queryFn: async () => {
      try {
        const data = await apiGetEquipos();
        const items = (data?.items ?? []).map(backendToEquipment);
        if (items.length === 0) {
          console.warn("[useEquipos] backend devolvió 0 items, fallback al mock");
          return { items: MOCK_EQUIPMENT, usingFallback: true };
        }
        return { items, usingFallback: false };
      } catch (err) {
        console.warn("[useEquipos] backend offline, fallback al mock:", err);
        return { items: MOCK_EQUIPMENT, usingFallback: true };
      }
    },
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  return {
    ...q,
    data: q.data?.items ?? [],
    usingFallback: q.data?.usingFallback ?? false,
  };
}

export function useCategorias() {
  return useQuery({
    queryKey: ["categorias"],
    queryFn: apiGetCategorias,
    staleTime: 10 * 60 * 1000,
  });
}

export function useDisponibilidad(startDate?: Date, endDate?: Date) {
  const desde = startDate ? format(startDate, "yyyy-MM-dd") : "";
  const hasta = endDate   ? format(endDate,   "yyyy-MM-dd") : "";

  return useQuery({
    queryKey: ["disponibilidad", desde, hasta],
    queryFn: async () => {
      try {
        return await apiGetDisponibilidad(desde, hasta);
      } catch (err) {
        console.warn("[useDisponibilidad] backend no responde:", err);
        return {} as Record<string, number>;
      }
    },
    enabled: !!(desde && hasta),
    staleTime: 2 * 60 * 1000,
    retry: 1,
  });
}
