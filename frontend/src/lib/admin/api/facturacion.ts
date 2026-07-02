/**
 * API de facturación electrónica ARCA (#1139).
 */
import { authedJson, authedPostJson } from "@/lib/authedFetch";

export type EmisorArca = {
  id: number;
  nombre: string;
  cuit: string;
  pto_vta: number;
  condicion_iva: "responsable_inscripto" | "monotributo" | "exento";
  cert_cargado: boolean;
  activo: boolean;
  razon_social: string | null;
  domicilio: string | null;
  iibb: string | null;
  inicio_actividades: string | null;
  notas: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type EstadoFacturacion = {
  ambiente: "homologacion" | "produccion";
  emisores: EmisorArca[];
};

export type FacturaEstado = "pendiente" | "emitida" | "error" | "anulada";

export type Factura = {
  id: number;
  pedido_id: number;
  emisor: string;
  ambiente: "homologacion" | "produccion";
  cbte_tipo: number;
  pto_vta: number;
  cbte_nro: number | null;
  cae: string | null;
  cae_vto: string | null;
  doc_tipo: number | null;
  doc_nro: number | null;
  condicion_iva_receptor: number | null;
  imp_neto: number;
  imp_iva: number;
  imp_total: number;
  moneda: string;
  cliente_cuit: string | null;
  razon_social: string | null;
  qr_payload: string | null;
  pdf_key: string | null;
  estado: FacturaEstado;
  nota_credito_de: number | null;
  errores: string[] | null;
  fecha_emision: string | null;
  created_at: string | null;
  created_by: string | null;
};

export type FacturasListResp = {
  facturas: Factura[];
  total_imp_total: number;
  count: number;
};

export type PadronResult =
  | {
      encontrado: true;
      razon_social: string;
      nombre: string;
      apellido: string;
      domicilio: string;
      condicion_iva: string;
      estado_clave: string;
    }
  | { encontrado: false };

export type ChequeoPreview = { check: string; ok: boolean; bloqueante: boolean; mensaje: string };

export type PreviewFactura = {
  ambiente: "homologacion" | "produccion";
  emisor: { nombre: string; cuit: number; condicion_iva: string };
  receptor: { doc_tipo: string; doc_nro: string; condicion_iva: string; razon_social: string };
  comprobante: { letra: string; tipo_nro: number; numero_a_emitir: number; pto_vta: number };
  importes: { neto: number; iva: number; total: number };
  fechas: {
    emision: string;
    servicio_desde: string | null;
    servicio_hasta: string | null;
    vto_pago: string | null;
  };
  chequeos: ChequeoPreview[];
  listo: boolean;
};

export const facturacionApi = {
  getEstado: () => authedJson<EstadoFacturacion>("/api/admin/facturacion/estado"),

  // Autocompletar razón social/domicilio/condición IVA desde el padrón ARCA.
  consultarPadron: (cuit: string) =>
    authedJson<PadronResult>(`/api/admin/arca/padron/${encodeURIComponent(cuit)}`),

  // Emisores
  listEmisores: () => authedJson<EmisorArca[]>("/api/admin/emisores-arca"),
  createEmisor: (body: Omit<EmisorArca, "id" | "cert_cargado" | "created_at" | "updated_at">) =>
    authedPostJson<EmisorArca>("/api/admin/emisores-arca", body),
  updateEmisor: (id: number, body: Partial<EmisorArca>) =>
    authedJson<EmisorArca>(`/api/admin/emisores-arca/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  cargarCert: (id: number, cert_pem: string, key_pem: string) =>
    authedPostJson<{ ok: boolean; cert_cargado: boolean }>(`/api/admin/emisores-arca/${id}/cert`, {
      cert_pem,
      key_pem,
    }),
  desactivarEmisor: (id: number) =>
    authedJson<void>(`/api/admin/emisores-arca/${id}`, { method: "DELETE" }),

  // Facturas
  previewFactura: (pedidoId: number) =>
    authedJson<PreviewFactura>(`/api/alquileres/${pedidoId}/facturar/preview`),
  facturarPedido: (pedidoId: number) =>
    authedPostJson<Factura>(`/api/alquileres/${pedidoId}/facturar`, {}),
  listFacturasPedido: (pedidoId: number) =>
    authedJson<Factura[]>(`/api/alquileres/${pedidoId}/facturas`),
  notaCreditoFactura: (facturaId: number) =>
    authedPostJson<Factura>(`/api/facturas/${facturaId}/nota-credito`, {}),
  enviarMailFactura: (facturaId: number) =>
    authedPostJson<{ ok: boolean; to: string }>(`/api/facturas/${facturaId}/enviar-mail`, {}),
  listFacturas: (params?: { emisor?: string; estado?: string; desde?: string; hasta?: string }) => {
    const sp = new URLSearchParams();
    if (params?.emisor) sp.set("emisor", params.emisor);
    if (params?.estado) sp.set("estado", params.estado);
    if (params?.desde) sp.set("desde", params.desde);
    if (params?.hasta) sp.set("hasta", params.hasta);
    const qs = sp.toString();
    return authedJson<FacturasListResp>(`/api/admin/facturas${qs ? `?${qs}` : ""}`);
  },
};
