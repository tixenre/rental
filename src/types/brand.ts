export interface Brand {
  id: number;
  nombre: string;
  logo_url?: string | null;
  /** Si true, el frontend público destaca esta marca en el BrandCarousel del home. #288 */
  destacada?: boolean;
  /** Orden manual del admin (ASC). Determina el orden del BrandCarousel
   *  cuando hay destacadas. Default 100. */
  orden?: number;
}

export interface MarcaAdmin {
  id: number;
  nombre: string;
  logo_url?: string | null;
  visible: boolean;
  /** Toggle de "marca destacada en home" — control manual del admin. #288 */
  destacada: boolean;
  orden: number;
  total: number;
}
