export interface Brand {
  id: number;
  nombre: string;
  logo_url?: string | null;
}

export interface MarcaAdmin {
  id: number;
  nombre: string;
  logo_url?: string | null;
  visible: boolean;
  orden: number;
  total: number;
}
