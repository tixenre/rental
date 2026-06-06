/**
 * cliente-nombre.ts — composición canónica del nombre visible de un cliente.
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
