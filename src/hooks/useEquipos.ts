import { useQuery } from "@tanstack/react-query";
import { apiGetEquipos, apiGetCategorias, apiGetDisponibilidad, type BackendEquipo } from "@/lib/api";
import { type Equipment } from "@/data/equipment";
import { format } from "date-fns";

/* ─── Adaptador backend → tipo frontend ─────────────────────────────── */

export function backendToEquipment(e: BackendEquipo): Equipment {
  const nombre = e.nombre ?? "";
  const marca  = e.marca  ?? "";
  const name   = [nombre, e.modelo].filter(Boolean).join(" ") || "Sin nombre";

  return {
    id: String(e.id),
    slug: `${marca}-${name}`
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || `equipo-${e.id}`,
    name,
    brand: marca || "—",
    // La primera etiqueta es la categoría principal; fallback a "Accesorios"
    category: ((e.etiquetas ?? [])[0] as Equipment["category"]) ?? "Accesorios",
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

export function useEquipos() {
  return useQuery({
    queryKey: ["equipos"],
    queryFn: async () => {
      const data = await apiGetEquipos();
      return data.items.map(backendToEquipment);
    },
    staleTime: 5 * 60 * 1000,
  });
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
    queryFn: () => apiGetDisponibilidad(desde, hasta),
    enabled: !!(desde && hasta),
    staleTime: 2 * 60 * 1000,
  });
}
