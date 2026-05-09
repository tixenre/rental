import { useQuery } from "@tanstack/react-query";
import { apiGetEquipos, apiGetCategorias, apiGetDisponibilidad, type BackendEquipo } from "@/lib/api";
import { type Equipment, type Category } from "@/data/equipment";
import { format } from "date-fns";

/* ─── Mapeo de etiquetas backend → categorías Lovable ─────────────────── */

const TAG_TO_CATEGORY: Record<string, Category> = {
  // Cámaras
  "cámara": "Cámaras",
  "camera": "Cámaras",
  "red": "Cámaras",
  "cinema": "Cámaras",
  "cinema line": "Cámaras",
  "dslr": "Cámaras",
  "mirrorless": "Cámaras",
  "canon": "Cámaras",
  "sony": "Cámaras",
  "gopro": "Cámaras",
  "insta360": "Cámaras",
  "acción": "Cámaras",

  // Lentes
  "lente": "Lentes",
  "lens": "Lentes",
  "zoom": "Lentes",
  "prime": "Lentes",
  "macro": "Lentes",
  "sigma": "Lentes",
  "laowa": "Lentes",

  // Monitores
  "monitor": "Monitores",
  "atomos": "Monitores",
  "smallhd": "Monitores",
  "lilliput": "Monitores",
  "hollyland": "Monitores",

  // Iluminación
  "luz": "Luces",
  "light": "Luces",
  "led": "Luces",
  "aputure": "Luces",
  "nanlite": "Luces",
  "amaran": "Luces",
  "godox": "Luces",
  "arri": "Luces",

  // Tungsteno
  "tungsteno": "Tungsteno",
  "fresnel": "Tungsteno",
  "lowel": "Tungsteno",

  // Modificadores
  "softbox": "Modificadores",
  "difusor": "Modificadores",
  "bandera": "Modificadores",
  "modificador": "Modificadores",
  "lantern": "Modificadores",

  // Comunicación
  "intercom": "Comunicación",
  "solidcom": "Comunicación",
  "comunicación": "Comunicación",

  // Flash
  "flash": "Flash",

  // Brazo Mágico
  "brazo": "Brazo Mágico",
  "magic arm": "Brazo Mágico",

  // Stands
  "stand": "Stands",
  "c-stand": "Stands",
  "roller": "Stands",
  "lowboy": "Stands",

  // Grips
  "grip": "Grips",
  "clamp": "Grips",
  "car mount": "Grips",
  "plate": "Grips",
  "mafer": "Grips",

  // Trípode
  "trípode": "Trípode",
  "tripod": "Trípode",
  "manfrotto": "Trípode",
  "sachtler": "Trípode",

  // Sonido
  "micrófono": "Sonido",
  "microphone": "Sonido",
  "shotgun": "Sonido",
  "lavalier": "Sonido",
  "wireless": "Sonido",
  "rode": "Sonido",
  "sony uwp": "Sonido",
  "zoom": "Sonido",
  "audio": "Sonido",
  "sound": "Sonido",

  // Baterías
  "batería": "Baterías",
  "battery": "Baterías",
  "vmount": "Baterías",
  "anton bauer": "Baterías",

  // Filtros
  "filtro": "Filtros",
  "filter": "Filtros",
  "nd": "Filtros",
  "tiffen": "Filtros",
};

function mapTagToCategory(tags: string[]): Category {
  if (!tags || tags.length === 0) return "Accesorios";

  // Buscar la primera etiqueta que tenga mapping
  for (const tag of tags) {
    const normalized = tag.toLowerCase().trim();
    // Búsqueda exacta
    if (TAG_TO_CATEGORY[normalized]) {
      return TAG_TO_CATEGORY[normalized];
    }
    // Búsqueda parcial (si la etiqueta contiene una clave del mapping)
    for (const [key, category] of Object.entries(TAG_TO_CATEGORY)) {
      if (normalized.includes(key) || key.includes(normalized)) {
        return category;
      }
    }
  }

  return "Accesorios";
}

/* ─── Adaptador backend → tipo frontend ─────────────────────────────── */

export function backendToEquipment(e: BackendEquipo): Equipment {
  const nombre = e.nombre ?? "";
  const marca  = e.marca  ?? "";
  const name   = [nombre, e.modelo].filter(Boolean).join(" ") || "Sin nombre";
  const category =
    ((e.etiquetas ?? [])[0] as Category | undefined) ??
    inferCategory(nombre, marca, e.modelo);

  return {
    id: String(e.id),
    slug: `${marca}-${name}`
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || `equipo-${e.id}`,
    name,
    brand: marca || "—",
    // Mapear etiquetas del backend a categorías de Lovable
    category: mapTagToCategory(e.etiquetas ?? []),
    pricePerDay: e.precio_jornada ?? 0,
    fotoUrl: e.foto_url ?? null,
    cantidad: e.cantidad ?? 1,
    description: "",
    specs: [],
    isNew: false,
    isCombo: false,
    includes: [],
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
