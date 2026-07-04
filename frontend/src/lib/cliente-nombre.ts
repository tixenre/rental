/**
 * cliente-nombre.ts — composición canónica del nombre/dirección visibles de
 * un cliente.
 *
 * Fuente ÚNICA del front. Antes el nombre se armaba "Apellido, Nombre" copiado
 * en ~6 lugares (listado, menú, detalle, selector de pedido, snapshot del
 * pedido). Decisión del dueño 2026-06-06: el nombre se muestra **"Nombre
 * Apellido"** (nombre primero) en todas las superficies. Espeja el helper
 * backend `routes/clientes.nombre_completo_cliente`.
 */

/** Devuelve "Nombre Apellido" (recortado). Si falta el apellido, solo el nombre. */
export function nombreCliente(c: { nombre?: string | null; apellido?: string | null }): string {
  const n = (c.nombre ?? "").trim();
  const a = (c.apellido ?? "").trim();
  return a ? `${n} ${a}`.trim() : n;
}

/** Nombre "legal" a mostrar: el de RENAPER si la identidad está verificada,
 *  si no el nombre base autodeclarado. Espeja `identity/__init__.py::
 *  nombre_validado` (misma regla "preferí RENAPER si está verificado") —
 *  fuente única, no duplicar el `if nombre_renaper …` en cada lector. */
export function nombreClienteLegal(c: {
  nombre?: string | null;
  apellido?: string | null;
  nombre_renaper?: string | null;
  apellido_renaper?: string | null;
}): string {
  if (c.nombre_renaper) {
    return `${c.nombre_renaper} ${c.apellido_renaper ?? ""}`.trim();
  }
  return nombreCliente(c);
}

/** Dirección "legal" a mostrar: la de RENAPER si está verificada, si no la
 *  base. Espeja `identity/__init__.py::direccion_validada` (misma regla). */
export function direccionClienteLegal(c: {
  direccion?: string | null;
  direccion_renaper?: string | null;
}): string | null {
  return c.direccion_renaper || c.direccion || null;
}
