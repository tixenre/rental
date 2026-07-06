/**
 * API de productoras (#1240) — entidad fiscal compartida entre cuentas de
 * cliente, sin login propio. El admin es el único que crea/edita/vincula;
 * el cliente solo la lee (`facturacionApi`-equivalente en `lib/cuit.ts`).
 */
import { authedFetch, authedJson, authedPostJson } from "@/lib/authedFetch";
import type { PerfilImpuestos } from "@/lib/iva";

export type Productora = {
  id: number;
  // Nullable (#1251 Fase 3): una productora puede nacer BORRADOR con solo
  // `nombre`, sin CUIT — no facturable hasta que se le asigne uno.
  cuit: string | null;
  perfil_impuestos: PerfilImpuestos | null;
  razon_social: string | null;
  domicilio_fiscal: string | null;
  email_facturacion: string | null;
  notas: string | null;
  // Manuales, no vienen de AFIP (#1251 Fase 2) — `nombre` es el label amigable
  // que siempre queda disponible aunque `razon_social` venga vacía de ARCA.
  nombre: string | null;
  redes_sociales: string | null;
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
  // `cuit` opcional (#1251 Fase 3) — sin CUIT crea un borrador (necesita `nombre`).
  crear: (cuit: string | undefined, notas?: string, nombre?: string, redes_sociales?: string) =>
    authedPostJson<Productora>("/api/admin/productoras", { cuit, notas, nombre, redes_sociales }),
  obtener: (id: number) => authedJson<ProductoraDetalle>(`/api/admin/productoras/${id}`),
  reverificar: (id: number) =>
    authedJson<Productora>(`/api/admin/productoras/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reverificar: true }),
    }),
  // Edita nombre/redes_sociales/notas SIN reverificar contra ARCA (esos 3 son
  // manuales, a diferencia de razón social/domicilio/condición IVA). `cuit`
  // solo tiene efecto si la productora todavía no tiene uno (completa un
  // borrador — #1251 Fase 3); reasignar un CUIT ya verificado no está soportado.
  actualizar: (
    id: number,
    data: { nombre?: string; redes_sociales?: string; notas?: string; cuit?: string },
  ) =>
    authedJson<Productora>(`/api/admin/productoras/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }),
  agregarMiembro: (id: number, clienteId: number) =>
    authedPostJson<{ ok: boolean }>(`/api/admin/productoras/${id}/miembros`, {
      cliente_id: clienteId,
    }),
  quitarMiembro: (id: number, clienteId: number) =>
    authedFetch(`/api/admin/productoras/${id}/miembros/${clienteId}`, { method: "DELETE" }),
};
