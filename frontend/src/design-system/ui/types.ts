/**
 * Tipos compartidos por los primitivos del DS (Pill, EstadoBadge, PagoBadge…).
 *
 * Viven acá, junto a las piezas que los usan en `design-system/ui/`.
 * Mantenelos en sync con el repo de producción (`src/data/*`) si crecen.
 */

export type EquipmentCategory =
  | "Cámaras"
  | "Lentes"
  | "Iluminación"
  | "Audio"
  | "Soportes"
  | "Accesorios"
  | "Adaptadores";

export interface AddonItem {
  id?: string;
  name: string;
  qty?: number;
}

export type { EstadoPedido } from "@/lib/pedido-estados";

export type CatalogView = "grid" | "list";
