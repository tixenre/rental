"""descuentos/queries/cliente.py — el descuento fijo de un cliente, en vivo.

Fase C-1 (#1219): antes, el descuento del cliente se copiaba una vez a
`alquileres.descuento_pct` al crear/asignar el pedido — un snapshot que
`propagar_descuento_a_presupuestos` tenía que sobreescribir a mano cada vez
que el cliente cambiaba su descuento (y de paso pisaba sin aviso cualquier
override manual que ya existiera). Ahora el pedido consulta el descuento del
cliente EN VIVO cada vez que hace falta (mismo patrón que "contacto en vivo",
MEMORIA 2026-06-06, extendido a la plata solo para el fallback sin override).
"""


def obtener_descuento_cliente(conn, cliente_id) -> float:
    """Descuento fijo (`clientes.descuento`) del cliente, leído fresco. 0.0 si
    no hay `cliente_id` o el cliente no existe."""
    if not cliente_id:
        return 0.0
    row = conn.execute(
        "SELECT descuento FROM clientes WHERE id = %s", (cliente_id,)
    ).fetchone()
    return float(row["descuento"] or 0) if row else 0.0
