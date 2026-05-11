export type DiagStep = { label: string; status: "pending" | "ok" | "fail" | "skip"; detail?: string };

export type EnriquecerResult = {
  marca: string | null;
  modelo: string | null;
  nombre_normalizado: string;
  descripcion: string;
  specs: { label: string; value: string }[];
  keywords: string[];
  foto_url: string | null;
  /** Todas las URLs de foto que pasaron la validación. La primera es la elegida por defecto. */
  foto_candidates?: string[];
  // Ficha extendida (cualquiera puede ser null si no se encontró)
  peso?: string | null;
  dimensiones?: string | null;
  montura?: string | null;
  formato?: string | null;
  resolucion?: string | null;
  alimentacion?: string | null;
  incluye?: string[];
  conectividad?: string[];
  compatible_con?: string[];
  video_url?: string | null;
  precio_bh_usd?: number | null;
  categoria_sugerida?: string | null;
  // Trazabilidad
  fuente_url: string;
  fuente_titulo: string;
  fuente_foto_url?: string | null;
  foto_motivo?: string | null;
  enriquecido_fuente?: string | null;
  raw?: Record<string, unknown>;
};
