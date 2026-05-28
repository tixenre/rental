/**
 * Tipos compartidos del dominio Rambla Rental.
 *
 * Si tu proyecto ya tiene `@/data/equipment` etc., reemplazá estos por los
 * tuyos. Estos son mínimos: lo que el kit consume para sus componentes
 * presentacionales.
 */

/**
 * Categorías del catálogo público.
 * Bautizadas tal cual los clientes las nombran.
 */
export type EquipmentCategory =
  | "Cámaras"
  | "Lentes"
  | "Iluminación"
  | "Audio"
  | "Soportes"
  | "Accesorios"
  | "Adaptadores";

/**
 * Un equipo del catálogo. Mínimo viable — el `Equipment` de producción
 * en el repo tiene más campos (specs, kit, fotos múltiples, etc).
 */
export interface Equipment {
  id: string;
  name: string;
  brand: string;
  category: EquipmentCategory | string;
  pricePerDay: number;
  /** URL de la foto. Si es null/undefined o falla, se muestra placeholder. */
  fotoUrl?: string | null;
  /** Stock total del equipo. 0 = sin stock. */
  cantidad: number;
  /** Badge "nuevo" arriba-izquierda de la card. */
  isNew?: boolean;
  /** Badge "★ destacado" arriba-derecha. */
  destacado?: boolean;
  /** Descripción larga, opcional, para fichas detalladas. */
  description?: string;
  /** Items que vienen incluidos (cuerpo + batería + cargador + …). */
  includes?: AddonItem[];
}

/**
 * Item del kit "incluye" que viene con un equipo.
 * Aparece en AddonPills y en la sección "Incluye" de la ficha.
 */
export interface AddonItem {
  /** Identificador estable (id en BD o slug). Sirve para el `key` de React. */
  id?: string;
  /** Texto visible. Truncado a 140px si es muy largo. */
  name: string;
  /** Cantidad. Si es > 1, aparece como badge ink/amber al final de la pill. */
  qty?: number;
}

/**
 * Estados del ciclo de vida de un pedido.
 *
 *   borrador     → cliente todavía editando
 *   presupuesto  → cotizado, esperando respuesta
 *   solicitado   → cliente confirmó, en cola del operador
 *   confirmado   → operador aprobó
 *   retirado     → en posesión del cliente
 *   entregado    → alias de retirado en algunas vistas
 *   devuelto     → cerrado OK
 *   finalizado   → cerrado OK, archivado
 *   cancelado    → no procedió
 */
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

/**
 * Vista del catálogo: grid de cards 4:5 o lista compacta con expansión.
 */
export type CatalogView = "grid" | "list";
