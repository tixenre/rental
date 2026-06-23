import { useQuery } from "@tanstack/react-query";
import {
  apiGetEquipos,
  apiGetCategorias,
  apiGetMarcs,
  type BackendEquipo,
  type BackendMarca,
} from "@/lib/api";
import {
  type Equipment,
  type Category,
  type ContenidoIncluidoItem,
  equipment as MOCK_EQUIPMENT,
} from "@/data/equipment";
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
  {
    keywords: [
      "batería",
      "bateria",
      "battery",
      "v-mount",
      "vmount",
      "np-f",
      "lp-e",
      "np-fz",
      "kit baterías",
      "kit bateria",
    ],
    category: "Baterías",
  },

  // Filtros
  {
    keywords: ["filtro", "filter", "polarizador", "difusión", "pro-mist", "tiffen"],
    category: "Filtros",
  },

  // Cámaras (antes de lentes para que "Canon" no matchee lentes)
  {
    keywords: [
      "cámara",
      "camara",
      "camera",
      "gopro",
      "insta360",
      "komodo",
      "fx3",
      "zv-e1",
      "a7 v",
      "c200",
      "cinema line",
    ],
    category: "Cámaras",
  },

  // Lentes
  {
    keywords: [
      "lente",
      "lens",
      "lentes",
      "kit lentes",
      "laowa",
      "tokina",
      "zeiss",
      "speedbooster",
      "montura",
    ],
    category: "Lentes",
  },

  // Monitores
  {
    keywords: ["monitor", "video assist", "smallhd", "lilliput", "viltrox", "atomos"],
    category: "Monitores",
  },

  // Comunicación
  { keywords: ["intercom", "solidcom", "hollyland"], category: "Comunicación" },

  // Flash
  { keywords: ["flash"], category: "Flash" },

  // Sonido (antes de "wireless" genérico)
  {
    keywords: [
      "micrófono",
      "microfono",
      "microphone",
      "lavalier",
      "shotgun",
      "wireless go",
      "dji mic",
      "rodecaster",
      "caña boom",
      "boom arm",
      "sennheiser",
      "zeppelin",
      "inalámbrico rode",
    ],
    category: "Sonido",
  },

  // Brazo Mágico
  {
    keywords: [
      "brazo mágico",
      "brazo magico",
      "brazo articulado",
      "brazo avenger",
      "brazo con rótula",
      "magic arm",
      "superflex",
    ],
    category: "Brazo Mágico",
  },

  // Stands
  { keywords: ["c-stand", "stand", "backdrop"], category: "Stands" },

  // Tungsteno (antes de "luz" genérico)
  {
    keywords: [
      "tungsteno",
      "fresnel tungsteno",
      "par mil",
      "mole richardson",
      "fresnel arri",
      "lowel",
    ],
    category: "Tungsteno",
  },

  // Modificadores de luz
  {
    keywords: [
      "softbox",
      "bandera negra",
      "frame difusión",
      "frame difusion",
      "reflector",
      "fresnel attachment",
      "globo china",
      "lantern",
      "modificador",
    ],
    category: "Modificadores",
  },

  // Luces (genérico, después de Tungsteno y Modificadores)
  {
    keywords: [
      "luz ",
      "luz led",
      "luz on-camera",
      "luz open face",
      "spotlight",
      "fresnel",
      "kino flo",
      "nanlite",
      "amaran",
      "aputure",
      "godox vl",
      "godox tl",
      "godox m1",
      "arri",
      "dracast",
      "yongnuo",
      "pampa tubo",
      "máquina de humo",
      "maquina de humo",
    ],
    category: "Luces",
  },

  // Trípode / movimiento
  {
    keywords: [
      "trípode",
      "tripode",
      "tripod",
      "manfrotto",
      "sachtler",
      "slider",
      "riel dolly",
      "dolly",
      "steadicam",
      "gimbal",
      "ronin",
      "glidecam",
      "follow focus",
      "nucleus",
    ],
    category: "Trípode",
  },

  // Grips
  {
    keywords: [
      "clamp",
      "car mount",
      "jaw clamp",
      "junior pin",
      "baby pin",
      "wall plate",
      "pinza",
      "sopapa",
      "matebox",
      "matte box",
    ],
    category: "Grips",
  },
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
  // El backend es single source of truth: si calculó el nombre_publico
  // (via el template configurado en /admin/specs), usamos eso.
  const backendNombre = (e.nombre_publico ?? "").trim();
  if (backendNombre) return backendNombre;

  // Sin template configurado (o template que rindió vacío) → fallback al
  // nombre interno. No replicamos el render del template en el frontend
  // — eso causaba inconsistencia entre lo que el admin veía aquí y lo
  // persistido del backend.
  const nombre = (e.nombre ?? "").trim();
  const modelo = (e.modelo ?? "").trim();
  if (nombre && modelo && !nombre.includes(modelo)) {
    return `${nombre} ${modelo}`;
  }
  return nombre || modelo || "Sin nombre";
}

/**
 * Formatea un value de spec para mostrar en el detalle público.
 * Si el value es JSON parseable y es array de objetos tipo tabla
 * (con celdas `{valor, unidad}` o escalares), se renderiza como texto
 * legible: "19389 lm · 5700 K" por fila, filas separadas por salto de línea.
 *
 * Si no parece JSON tabla, se devuelve la string original tal cual.
 */
export function formatSpecValueForDisplay(raw: unknown): string {
  if (raw == null) return "";
  // Si ya es string que no parece JSON, return as-is.
  const str = typeof raw === "string" ? raw : String(raw);
  const trimmed = str.trim();
  if (!trimmed.startsWith("[") && !trimmed.startsWith("{")) return str;
  try {
    const parsed = JSON.parse(trimmed);
    if (!Array.isArray(parsed) || parsed.length === 0) return str;
    const lines: string[] = [];
    for (const row of parsed) {
      if (!row || typeof row !== "object") continue;
      const cells: string[] = [];
      for (const v of Object.values(row)) {
        if (v == null || v === "") continue;
        if (typeof v === "object" && "valor" in v) {
          const vv = v as { valor: unknown; unidad?: unknown };
          const valor = vv.valor == null ? "" : String(vv.valor);
          const unidad = vv.unidad ? String(vv.unidad).trim() : "";
          const cell = unidad ? `${valor} ${unidad}` : valor;
          if (cell.trim()) cells.push(cell);
        } else {
          const cell = String(v).trim();
          if (cell) cells.push(cell);
        }
      }
      if (cells.length > 0) lines.push(cells.join(" · "));
    }
    return lines.length > 0 ? lines.join("\n") : str;
  } catch {
    return str;
  }
}

/* ─── Adaptador backend → tipo frontend ─────────────────────────────── */

export function backendToEquipment(e: BackendEquipo): Equipment {
  const nombre = e.nombre ?? "";
  const marca = e.marca ?? "";
  const publicName = buildPublicName(e);
  const fallbackName = [nombre, e.modelo].filter(Boolean).join(" ") || "Sin nombre";
  const name = publicName || fallbackName;

  const ficha = e.ficha;
  type ParsedSpec = {
    label: string;
    value: string;
    value_raw?: string;
    output_config?: { row_strategy?: "all" | "first" | "last" } | null;
  };
  let parsedSpecs: ParsedSpec[] = [];

  // Fase E: specs estructuradas desde equipo_specs (fuente única).
  // El fallback a `ficha.specs_json` se eliminó — esa columna fue
  // droppeada en la migration de Fase E.
  if (e.specs && Object.keys(e.specs).length > 0) {
    parsedSpecs = Object.values(e.specs)
      .filter((s) => s.value != null && String(s.value).trim() !== "")
      .filter((s) => {
        if (s.tipo !== "bool") return true;
        const v = String(s.value).toLowerCase();
        return v === "sí" || v === "si" || v === "true" || v === "1";
      })
      .sort((a, b) => (a.prioridad ?? 999) - (b.prioridad ?? 999))
      .map((s) => ({
        label: s.label,
        // `value_display` viene renderizado del backend (mismo renderer que el
        // nombre público: rango/unidad/prefijo). Fallback al formateo local
        // (que cubre tablas) para entries sin value_display.
        value: s.value_display ?? formatSpecValueForDisplay(s.value),
      }));
  }

  // Fase F: fuente única es e.specs (equipo_specs). Sin fallback a
  // columnas legacy de ficha — esas fueron migradas con backfill y
  // droppeadas en la migration a1b3c5e7f9d2.
  const specByKey = (key: string): string | null => {
    const s = e.specs?.[key];
    return s && s.value != null && String(s.value).trim() !== "" ? String(s.value) : null;
  };

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
  const parsedIncluye = parseStringList(ficha?.incluye_json);
  const parsedConectividad = parseStringList(ficha?.conectividad_json);
  const parsedCompatibleCon = parseStringList(ficha?.compatible_con_json);

  let parsedContenidoIncluido: ContenidoIncluidoItem[] = [];
  if (ficha?.contenido_incluido_json) {
    try {
      const arr = JSON.parse(ficha.contenido_incluido_json);
      if (Array.isArray(arr)) {
        parsedContenidoIncluido = arr.filter(
          (v): v is ContenidoIncluidoItem =>
            v != null &&
            typeof v === "object" &&
            typeof v.nombre === "string" &&
            typeof v.cantidad === "number",
        );
      }
    } catch {
      /* ignore */
    }
  }

  const kit = Array.isArray(e.kit)
    ? (e.kit as Array<{
        componente_id: number;
        nombre: string;
        cantidad: number;
        foto_url?: string | null;
        esencial?: boolean | null;
        descuento_pct?: number | null;
      }>)
    : [];
  const includes = kit.map((k) => ({
    id: String(k.componente_id),
    name: k.nombre,
    qty: k.cantidad,
    fotoUrl: k.foto_url ?? null,
    esencial: k.esencial ?? true,
  }));

  return {
    id: String(e.id),
    slug:
      `${marca}-${nombre}`
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "") || `equipo-${e.id}`,
    name,
    brand: marca || "—",
    category: e.categorias?.[0]?.nombre ?? resolveCategory(e.etiquetas ?? [], nombre, marca),
    categorias: e.categorias ?? [],
    pricePerDay: e.precio_jornada ?? 0,
    fotoUrl: e.foto_url ?? null,
    fotoUrlSm: e.foto_url_sm ?? null,
    fotos: (e.fotos ?? []).map((f) => ({ url: f.url, esPrincipal: !!f.es_principal })),
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
    // Ficha extendida — fuente única equipo_specs (Fase F).
    peso: specByKey("peso_g"),
    dimensiones: specByKey("dimensions_mm"),
    montura: specByKey("lens_mount"),
    formato: specByKey("formato"),
    resolucion: specByKey("resolucion_max"),
    alimentacion: specByKey("alimentacion"),
    incluye: parsedIncluye,
    conectividad: parsedConectividad,
    compatibleCon: parsedCompatibleCon,
    contenidoIncluido: parsedContenidoIncluido,
    videoUrl: ficha?.video_url ?? null,
    precioBhUsd: ficha?.precio_bh_usd ?? null,
    disponible: e.disponible,
    tipo: e.tipo,
    // Dict raw de specs estructuradas (Fase H: filtros públicos).
    // Cada entry tiene {value, label, tipo, prioridad, en_filtros, ...}
    // para que el catálogo arme filtros dinámicos.
    specsRaw: e.specs ?? {},
  };
}

/* ─── Filtros dinámicos por specs (Fase H) ──────────────────────────── */

export type SpecFilterDef = {
  /** spec_key del registry, ej. "lens_mount". */
  key: string;
  /** Label visible al usuario, ej. "Montura". */
  label: string;
  /** Valores únicos presentes en el dataset filtrado, ordenados alfa. */
  values: string[];
  /** prioridad del template (menor = más arriba en la UI). */
  prioridad: number;
};

/** Descubre qué specs son filtrables para el conjunto de equipos dado.
 *  Solo incluye specs con `en_filtros=true` en el template y al menos
 *  2 valores únicos presentes (filtrar por 1 valor no aporta). */
export function discoverFilterableSpecs(equipos: Equipment[]): SpecFilterDef[] {
  // Acumulamos {spec_key: {label, prioridad, values: Set}}
  const acc = new Map<
    string,
    {
      label: string;
      prioridad: number;
      values: Set<string>;
    }
  >();
  for (const eq of equipos) {
    const specsRaw = eq.specsRaw || {};
    for (const [key, s] of Object.entries(specsRaw)) {
      if (!s.en_filtros) continue;
      // Solo `enum` (opciones cerradas) → chips limpios y acotados. Los
      // `string` son texto libre (codecs, conexiones, grabación) y generaban
      // facetas basura con valores únicos larguísimos. number/rango/multi_enum
      // (sliders/facetas) quedan para el sistema de filtros completo (pendiente).
      if (s.tipo !== "enum") continue;
      const val = String(s.value || "").trim();
      if (!val) continue;
      if (!acc.has(key)) {
        acc.set(key, { label: s.label, prioridad: s.prioridad, values: new Set() });
      }
      acc.get(key)!.values.add(val);
    }
  }
  return Array.from(acc.entries())
    .filter(([, v]) => v.values.size >= 2)
    .map(([key, v]) => ({
      key,
      label: v.label,
      prioridad: v.prioridad,
      values: Array.from(v.values).sort((a, b) => a.localeCompare(b, "es")),
    }))
    .sort((a, b) => a.prioridad - b.prioridad);
}

/* ─── Hooks ─────────────────────────────────────────────────────────── */

type EquiposQueryResult = { items: Equipment[]; usingFallback: boolean };

export function useEquipos(startDate?: Date, endDate?: Date) {
  const desde = startDate ? format(startDate, "yyyy-MM-dd") : undefined;
  const hasta = endDate ? format(endDate, "yyyy-MM-dd") : undefined;

  const q = useQuery<EquiposQueryResult>({
    queryKey: ["equipos", desde, hasta],
    queryFn: async () => {
      const data = await apiGetEquipos({ desde, hasta });
      const items = (data?.items ?? []).map(backendToEquipment);
      return { items, usingFallback: false };
    },
    // staleTime corto (30s) para que los cambios desde back-office se reflejen
    // rápido en el catálogo público. Sin esto, el cliente podía ver datos
    // viejos hasta 5min después de un cambio del admin.
    staleTime: 30_000,
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
    staleTime: 60_000,
  });
}

export function useMarcas() {
  return useQuery<{ items: BackendMarca[] }>({
    queryKey: ["marcas"],
    queryFn: apiGetMarcs,
    staleTime: 60_000,
    retry: 1,
  });
}
