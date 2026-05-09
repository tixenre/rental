import { useQuery } from "@tanstack/react-query";
import { apiGetEquipos, apiGetCategorias, apiGetDisponibilidad, type BackendEquipo } from "@/lib/api";
import { equipment as MOCK_EQUIPMENT, type Equipment, type Category } from "@/data/equipment";
import { format } from "date-fns";

/* ─── Inferencia de categoría a partir del nombre/marca ──────────────
 * El backend hoy devuelve `etiquetas: []`. Mientras tanto inferimos
 * heurísticamente para que la UI muestre las secciones correctas.
 */
const CATEGORY_RULES: { cat: Category; needles: string[] }[] = [
  { cat: "Cámaras",       needles: ["camara", "cámara", "fx3", "fx6", "komodo", "ronin", "blackmagic", "alpha", "a7", "ursa", "zve", "insta360", "c200", "c300", "c70", "r5", "r6"] },
  { cat: "Lentes",        needles: ["lente", "lens", "prime", "zoom", "rf ", "ef ", "fe ", "gm ", "art ", "sigma", "macro", "tamron", "samyang", "rokinon", "16-35", "24-70", "70-200", "12-24", "18-35", "50mm", "85mm", "35mm", "24mm", "adaptador"] },
  { cat: "Monitores",     needles: ["monitor", "ninja", "smallhd", "lilliput", "atomos"] },
  { cat: "Tungsteno",     needles: ["tungsteno", "fresnel", "arri", "lowel"] },
  { cat: "Modificadores", needles: ["softbox", "lantern", "bandera", "difusor", "frame", "light dome", "bowens", "octa"] },
  { cat: "Comunicación",  needles: ["intercom", "solidcom", "headset"] },
  { cat: "Flash",         needles: ["flash", "speedlight", "v100", "ad200", "ad400", "ad600"] },
  { cat: "Brazo Mágico",  needles: ["brazo magico", "brazo mágico", "magic arm"] },
  { cat: "Stands",        needles: ["c-stand", "c stand", "lowboy", "roller stand", "pie de luz"] },
  { cat: "Grips",         needles: ["clamp", "mafer", "super clamp", "car mount", "baby pin", "magic arm", "rigging"] },
  { cat: "Trípode",       needles: ["tripode", "trípode", "sachtler", "manfrotto 504", "manfrotto 190", "fluido"] },
  { cat: "Sonido",        needles: ["microfono", "micrófono", "mic ", "rode", "shotgun", "lavalier", "lapel", "wireless go", "zoom h", "grabador", "ntg"] },
  { cat: "Baterías",      needles: ["bateria", "batería", "vmount", "v-mount", "lp-e6", "anton bauer", "cargador"] },
  { cat: "Filtros",       needles: ["filtro", "nd ", "promist", "polarizador", "tiffen"] },
  { cat: "Luces",         needles: ["led", "luz", "aputure", "nanlite", "amaran", "godox tubo", "rgb", "panel", "p300", "300x", "300d", "600d", "forza", "tl60", "mc pro", "nova"] },
];

function inferCategory(nombre: string, marca: string, modelo?: string | null): Category {
  const haystack = `${marca} ${nombre} ${modelo ?? ""}`.toLowerCase();
  for (const { cat, needles } of CATEGORY_RULES) {
    if (needles.some((n) => haystack.includes(n))) return cat;
  }
  return "Cámaras"; // fallback razonable; mejor que "Accesorios" inexistente
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
    category,
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
