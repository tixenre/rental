import { authedFetch } from "@/lib/authedFetch";
import { invalidateClienteSession } from "@/lib/iva";
import type { Perfil } from "./ClientePortalTypes";

/** PATCH parcial a /api/cliente/me; refleja la respuesta en el perfil. Punto único
 *  de guardado del perfil (lo comparten Contacto y Facturación). */
export async function patchPerfil(
  perfil: Perfil,
  onPerfilChange: (p: Perfil) => void,
  body: Record<string, unknown>,
  { invalidate = false }: { invalidate?: boolean } = {},
) {
  const res = await authedFetch("/api/cliente/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail ?? `Error ${res.status}`);
  }
  const updated = (await res.json()) as Perfil;
  onPerfilChange({ ...perfil, ...updated });
  // El perfil fiscal cambia cómo se cotiza el IVA en catálogo / carrito / ficha.
  if (invalidate) invalidateClienteSession();
}
