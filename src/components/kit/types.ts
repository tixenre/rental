/**
 * Tipos compartidos por los componentes del kit Rambla.
 *
 * Origen: `docs/design-kit/kit/types/equipment.ts`. Los duplico acá para
 * que `src/components/kit/*` sean drop-in sin acoplarse al snapshot del
 * design-kit. Mantenelos en sync con el repo de producción (`src/data/*`)
 * si crecen.
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
