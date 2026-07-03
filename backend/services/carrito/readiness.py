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


def equipo_visible_catalogo(conn, equipo_id: int) -> None:
    """Gate de seguridad único: valida que `equipo_id` sea un producto real y
    público del catálogo — vivo (`eliminado_at IS NULL`), `visible_catalogo = 1`,
    NO el recurso interno del Estudio (`es_recurso_interno = FALSE`, el
    "centinela" que modela el espacio físico — ver MEMORIA 2026-05-27/05-31) y
    con precio definido.

    Extraído (#1209) para que la creación de pedido del cliente
    (`precios_catalogo_para_reserva`, abajo) y la MODIFICACIÓN de un pedido ya
    existente (`cliente_portal/solicitudes.py::cliente_modificar_pedido`)
    apliquen EXACTAMENTE el mismo chequeo — antes solo lo aplicaba la creación:
    un cliente podía, vía `POST .../modificacion`, agregar a un presupuesto un
    equipo oculto/interno (o inexistente/soft-deleted) que la creación sí
    hubiera rechazado, reservando stock de un recurso que el negocio nunca
    ofreció públicamente.

    Lanza ``HTTPException(404)`` si el equipo no existe, está soft-deleted, no
    está visible, es el recurso interno, o no tiene precio definido (no se
    crean/agregan líneas de pedido con equipos fantasma).
    """
    row = conn.execute(
        "SELECT 1 FROM equipos "
        "WHERE id = %s AND eliminado_at IS NULL AND visible_catalogo = 1 "
        "AND es_recurso_interno = FALSE AND precio_jornada IS NOT NULL",
        (equipo_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, f"Equipo {equipo_id} no encontrado en el catálogo")


def precios_catalogo_para_reserva(conn, items) -> dict[int, int]:
    """Mapa `equipo_id → precio efectivo por jornada` para los ítems de un carrito
    que va a convertirse en pedido del cliente.

    **Gate de seguridad** (defensa en profundidad, `equipo_visible_catalogo`):
    solo equipos vivos y visibles del catálogo, con precio definido — sin esto
    un cliente podía reservar por API un equipo oculto/interno enumerando ids →
    pedido $0. El cliente **nunca** decide el precio: se descarta el
    `precio_jornada` del body y se toma el del catálogo, resuelto por la fuente
    única (`precio_jornada_efectivo`) → lo que el carrito cotiza es lo que se
    persiste (sin drift de combos).

    Lanza ``HTTPException(404)`` si un ítem no está en el catálogo público (no se
    crean pedidos con equipos fantasma). ``items``: iterable con ``.equipo_id``.
    """
    precios: dict[int, int] = {}
    for it in items:
        if it.equipo_id in precios:
            continue
        equipo_visible_catalogo(conn, it.equipo_id)
        precios[it.equipo_id] = int(precio_jornada_efectivo(conn, it.equipo_id) or 0)
    return precios
