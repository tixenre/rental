/**
 * API de productoras (#1240) — entidad fiscal compartida entre cuentas de
 * cliente, sin login propio. El admin es el único que crea/edita/vincula;
 * el cliente solo la lee (`facturacionApi`-equivalente en `lib/cuit.ts`).
 */
import { authedFetch, authedJson, authedPostJson } from "@/lib/authedFetch";
import type { PerfilImpuestos } from "@/lib/iva";

export type Productora = {
  id: number;
  cuit: string;
  perfil_impuestos: PerfilImpuestos;
  razon_social: string | null;
  domicilio_fiscal: string | null;
  email_facturacion: string | null;
  notas: string | null;
  verificado_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type Miembro = { id: number; nombre: string; apellido: string; email: string };

export type ProductoraDetalle = Productora & { miembros: Miembro[] };

export const productorasApi = {
  listar: (q?: string) =>
    authedJson<Productora[]>(`/api/admin/productoras${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  // Alta bloqueante: 422 si ARCA no confirma el CUIT (ver services.facturacion.padron).
  crear: (cuit: string, notas?: string) =>
    authedPostJson<Productora>("/api/admin/productoras", { cuit, notas }),
  obtener: (id: number) => authedJson<ProductoraDetalle>(`/api/admin/productoras/${id}`),
  reverificar: (id: number) =>
    authedJson<Productora>(`/api/admin/productoras/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reverificar: true }),
    }),
  agregarMiembro: (id: number, clienteId: number) =>
    authedPostJson<{ ok: boolean }>(`/api/admin/productoras/${id}/miembros`, {
      cliente_id: clienteId,
    }),
  quitarMiembro: (id: number, clienteId: number) =>
    authedFetch(`/api/admin/productoras/${id}/miembros/${clienteId}`, { method: "DELETE" }),
};
