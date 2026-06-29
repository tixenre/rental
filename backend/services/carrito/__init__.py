"""Paquete `services.carrito` — la lógica del carrito (la intención del cliente: "esto
es lo que quiero reservar"). Fuente única; ver `docs/SISTEMA_CARRITO.md`.

Patrón del repo: route = transporte, service = lógica. El carrito OWNA su selección /
estado / compartir / listas / readiness y REFERENCIA los motores (reservas = stock,
services.precios = plata, services.contenido = qué-incluye, create_pedido = creación).

Esta fase (F2, epic #1110) trae la SELECCIÓN canónica + el normalizar único; el resto
de los submódulos (activos, compartido, listas, readiness) se incorpora fase por fase.
F4 sumó `activos` (estado server-side: heartbeat / abandono / métricas).
"""
from services.carrito.activos import (
    ABANDONO_HORAS,
    heartbeat_upsert,
    listar_carritos_admin,
    marcar_confirmado,
)
from services.carrito.modelos import CANTIDAD_MAX, MAX_ITEMS, SeleccionItem
from services.carrito.seleccion import (
    a_items_json,
    a_tuplas,
    desde_items_json,
    normalizar_seleccion,
)

__all__ = [
    "SeleccionItem",
    "CANTIDAD_MAX",
    "MAX_ITEMS",
    "normalizar_seleccion",
    "a_items_json",
    "desde_items_json",
    "a_tuplas",
    "ABANDONO_HORAS",
    "heartbeat_upsert",
    "listar_carritos_admin",
    "marcar_confirmado",
]
