"""services/carrito/readiness.py — "el carrito listo para reservar" (lado plata).

Puerta del carrito **previa** a crear la reserva: resuelve el precio de cada ítem
con el gate de seguridad —solo equipos de `visible_catalogo`, el cliente NUNCA
decide el precio— apoyándose en la fuente única de plata
`services.precios.precio_jornada_efectivo` (combo → derivado de componentes;
kit/simple → su precio propio).

**No crea la reserva.** La creación real (con advisory-lock, motor sagrado) sigue
siendo `create_pedido_retry` (`routes/alquileres/core.py`): el route hace el
*handoff* con los precios que devuelve esta función. Así el carrito **pide** plata y
**delega** la creación; no se come ninguna de las dos. Ver `docs/SISTEMA_CARRITO.md`
(invariante "carrito = intención, gate = verdad").
"""
from fastapi import HTTPException

from services.precios import precio_jornada_efectivo


def precios_catalogo_para_reserva(conn, items) -> dict[int, int]:
    """Mapa `equipo_id → precio efectivo por jornada` para los ítems de un carrito
    que va a convertirse en pedido del cliente.

    **Gate de seguridad** (defensa en profundidad): solo equipos de
    `visible_catalogo` con precio definido — sin esto un cliente podía reservar por
    API un equipo oculto/interno enumerando ids → pedido $0. El cliente **nunca**
    decide el precio: se descarta el `precio_jornada` del body y se toma el del
    catálogo, resuelto por la fuente única (`precio_jornada_efectivo`) → lo que el
    carrito cotiza es lo que se persiste (sin drift de combos).

    Lanza ``HTTPException(404)`` si un ítem no está en el catálogo público (no se
    crean pedidos con equipos fantasma). ``items``: iterable con ``.equipo_id``.
    """
    precios: dict[int, int] = {}
    for it in items:
        if it.equipo_id in precios:
            continue
        # SELECT-gate de seguridad (visible_catalogo + precio no nulo). El precio
        # EFECTIVO lo pone el resolutor único, no este SELECT.
        row = conn.execute(
            "SELECT precio_jornada FROM equipos "
            "WHERE id = %s AND visible_catalogo = 1 AND precio_jornada IS NOT NULL",
            (it.equipo_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, f"Equipo {it.equipo_id} no encontrado en el catálogo")
        precios[it.equipo_id] = int(precio_jornada_efectivo(conn, it.equipo_id) or 0)
    return precios
