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

export type EstadoPedido =
  | "borrador"
  | "presupuesto"
  | "solicitado"
  | "confirmado"
  | "retirado"
  | "entregado"
  | "devuelto"
  | "finalizado"
  | "cancelado";

export type CatalogView = "grid" | "list";
