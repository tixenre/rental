export interface Brand {
  id: number;
  nombre: string;
  logo_url?: string | null;
  /** Si true, el frontend público destaca esta marca en el BrandCarousel del home. #288 */
  destacada?: boolean;
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
