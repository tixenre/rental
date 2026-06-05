/**
 * Tipos compartidos por los componentes del kit Rambla.
 *
 * Duplicados acá para que `src/components/kit/*` sean drop-in.
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
