import type { Equipment } from "@/data/equipment";

/**
 * Mock determinístico de disponibilidad — sustituir por backend real.
 * Cada item "no disponible" en ciertos rangos según hash(id + día).
 */
function hash(s: string) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export type Availability = {
  available: boolean;
  stock: number; // unidades libres
  reason?: string;
};

export function getAvailability(
  item: Pick<Equipment, "id">,
  start?: Date,
  end?: Date,
): Availability {
  if (!start || !end) return { available: true, stock: 3 };
  const startKey = Math.floor(start.getTime() / 86400000);
  const endKey = Math.floor(end.getTime() / 86400000);
  const seed = hash(item.id + ":" + startKey + ":" + endKey);

  // ~15% sin stock, ~20% stock bajo (1), resto stock cómodo (2-4)
  const bucket = seed % 100;
  if (bucket < 15) {
    return {
      available: false,
      stock: 0,
      reason: "No disponible en estas fechas",
    };
  }
  if (bucket < 35) return { available: true, stock: 1 };
  return { available: true, stock: 2 + (seed % 3) };
}
