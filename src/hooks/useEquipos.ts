import { useQuery } from "@tanstack/react-query";
import { apiGetEquipos, apiGetCategorias, apiGetDisponibilidad, apiGetMarcs, type BackendEquipo, type BackendMarca } from "@/lib/api";
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

export function buildPublicName(e: BackendEquipo): string {
  // 1) Si el backend ya calculó el nombre_publico (PR B/D del rediseño),
  // lo usamos directamente. Es la single source of truth.
  const backendNombre = ((e as unknown as { nombre_publico?: string | null }).nombre_publico ?? "").trim();
  if (backendNombre) return backendNombre;

  const tipo = e.categorias?.[0]?.nombre?.trim() ?? "";
  const marca = (e.marca ?? "").trim();
  const modelo = (e.modelo ?? "").trim();
  const nombre = (e.nombre ?? "").trim();
  const f = e.ficha;
  const montura = (f?.montura ?? "").trim();
  const formato = (f?.formato ?? "").trim();
  const resolucion = (f?.resolucion ?? "").trim();

  // 1) Si hay template editable, lo renderizamos.
  const tpl = (f?.nombre_publico_template ?? "").trim();
  if (tpl) {
    const vars: Record<string, string> = {
      tipo, marca, modelo, nombre, montura, formato, resolucion,
    };
    const rendered = renderNameTemplate(tpl, vars);
    if (rendered) return rendered;
  }

  // 2) Auto-build clásico.
  const parts = [tipo, marca, modelo, montura, formato, resolucion]
    .map((s) => s.replace(/\s+/g, " ").trim())
    .filter(Boolean);

  if (parts.length === 0) {
    return e.nombre || "Sin nombre";
  }
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

/**
 * Reemplaza tokens {clave} (case-insensitive) por su valor.
 * Si un token está vacío, se borra junto con el separador inmediato
 * (espacio, guion, em-dash, coma, slash, pipe) para no dejar "Sony — ".
 * Devuelve "" si el resultado quedó vacío o solo separadores.
 */
function renderNameTemplate(tpl: string, vars: Record<string, string>): string {
  // Normalizar claves a lowercase
  const lower: Record<string, string> = {};
  for (const k of Object.keys(vars)) lower[k.toLowerCase()] = vars[k] ?? "";

  // 1) Reemplazar tokens conocidos vacíos junto con el separador adyacente.
  //    Patrón: separador (opcional) + {token} O {token} + separador (opcional)
  const SEP = "[\\s\\-–—,/|·]";
  let out = tpl.replace(
    new RegExp(`(${SEP}+)?\\{([a-zA-Z_]+)\\}(${SEP}+)?`, "g"),
    (_m, before: string | undefined, key: string, after: string | undefined) => {
      const k = key.toLowerCase();
      if (!(k in lower)) return _m; // token desconocido → literal
      const val = lower[k].trim();
      if (val) return `${before ?? ""}${val}${after ?? ""}`;
      // Vacío: comemos UN separador (preferimos el de la derecha)
      if (after) return before ?? "";
      if (before) return "";
      return "";
    },
  );

  // 2) Limpiar separadores duplicados o sueltos al inicio/final
  out = out.replace(/\s+/g, " ").trim();
  out = out.replace(new RegExp(`^${SEP}+|${SEP}+$`, "g"), "").trim();
  out = out.replace(new RegExp(`(${SEP})\\s*\\1+`, "g"), "$1");

  // Si solo quedaron separadores → vacío
  if (!out || /^[\s\-–—,/|·]+$/.test(out)) return "";
  return out;
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

  let parsedKeywords: string[] = [];
  if (ficha?.keywords_json) {
    try {
      const arr = JSON.parse(ficha.keywords_json);
      if (Array.isArray(arr)) {
        parsedKeywords = arr
          .filter((k) => typeof k === "string" && k.trim())
          .map((k: string) => k.trim());
      }
    } catch {
      /* ignore */
    }
  }

  // Helper para parsear listas JSON guardadas como TEXT
  const parseStringList = (raw: string | null | undefined): string[] => {
    if (!raw) return [];
    try {
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return [];
      return arr
        .filter((v): v is string => typeof v === "string" && v.trim().length > 0)
        .map((v) => v.trim());
    } catch {
      return [];
    }
  };
  const parsedIncluye        = parseStringList(ficha?.incluye_json);
  const parsedConectividad   = parseStringList(ficha?.conectividad_json);
  const parsedCompatibleCon  = parseStringList(ficha?.compatible_con_json);

  const kit = Array.isArray(e.kit) ? e.kit as Array<{ componente_id: number; nombre: string; cantidad: number; foto_url?: string | null }> : [];
  const includes = kit.map((k) => ({
    id: String(k.componente_id),
    name: k.nombre,
    qty: k.cantidad,
    fotoUrl: k.foto_url ?? null,
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
    specsDestacados: e.specs_destacados ?? [],
    keywords: parsedKeywords,
    isNew: false,
    relevanciaManual: e.relevancia_manual ?? 100,
    destacado: (e.relevancia_manual ?? 100) <= 30,
    includes,
    _backendId: e.id,
    // Ficha extendida
    peso:           ficha?.peso          ?? null,
    dimensiones:    ficha?.dimensiones   ?? null,
    montura:        ficha?.montura       ?? null,
    formato:        ficha?.formato       ?? null,
    resolucion:     ficha?.resolucion    ?? null,
    alimentacion:   ficha?.alimentacion  ?? null,
    incluye:        parsedIncluye,
    conectividad:   parsedConectividad,
    compatibleCon:  parsedCompatibleCon,
    videoUrl:       ficha?.video_url     ?? null,
    precioBhUsd:    ficha?.precio_bh_usd ?? null,
  };
}

/* ─── Hooks ─────────────────────────────────────────────────────────── */

type EquiposQueryResult = { items: Equipment[]; usingFallback: boolean };

export function useEquipos() {
  const q = useQuery<EquiposQueryResult>({
    queryKey: ["equipos"],
    queryFn: async () => {
      const data = await apiGetEquipos();
      const items = (data?.items ?? []).map(backendToEquipment);
      return { items, usingFallback: false };
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

export function useMarcas() {
  return useQuery<{ items: BackendMarca[] }>({
    queryKey: ["marcas"],
    queryFn: apiGetMarcs,
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });
}
