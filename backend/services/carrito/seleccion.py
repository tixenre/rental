"""Selección canónica del carrito — la FORMA y la VALIDACIÓN únicas de "una lista de
equipos que el cliente quiere reservar".

`normalizar_seleccion` es la fuente ÚNICA de validación (dedup / clamp / filtro a
equipos existentes / cap / orden) que antes vivía DUPLICADA byte-por-byte en
`routes/compartir.py::_normalizar_items` y `routes/cliente_portal/listas.py::_normalizar_items`
(con los caps copiados). Los consumidores la importan en vez de redefinirla — lo hace
cumplir `tests/test_carrito_normalizar_safety.py` (candado, F3).

Funciones que reciben `conn` (no objetos con estado), igual que el resto del repo.
"""
import json

from services.carrito.modelos import CANTIDAD_MAX, MAX_ITEMS, SeleccionItem


def _eid_cant(it) -> tuple[int, int]:
    """Lee (equipo_id, cantidad) de un ítem, sea Pydantic (CartItem / CompartirItemIn /
    ListaItemIn / SeleccionItem) o dict — para no atar el normalizador a un tipo de entrada."""
    if isinstance(it, dict):
        return int(it["equipo_id"]), int(it.get("cantidad", 1))
    return int(it.equipo_id), int(getattr(it, "cantidad", 1))


def normalizar_seleccion(conn, items) -> list[SeleccionItem]:
    """Dedup por equipo_id (última cantidad gana), clamp `1..CANTIDAD_MAX`, filtro a
    equipos existentes (un equipo borrado del catálogo no entra), cap a `MAX_ITEMS`,
    preservando el orden de inserción (orden del carrito). Devuelve la selección canónica.

    Fuente ÚNICA de validación de la selección del carrito.
    """
    dedup: dict[int, int] = {}
    for it in items:
        eid, cant = _eid_cant(it)
        dedup[eid] = max(1, min(cant, CANTIDAD_MAX))
    if not dedup:
        return []
    existentes = {
        r["id"]
        for r in conn.execute(
            "SELECT id FROM equipos WHERE id = ANY(%s)", (list(dedup.keys()),)
        ).fetchall()
    }
    out = [
        SeleccionItem(equipo_id=eid, cantidad=cant)
        for eid, cant in dedup.items()
        if eid in existentes
    ]
    return out[:MAX_ITEMS]


def a_items_json(items: list[SeleccionItem]) -> str:
    """Serializa la selección a la forma de `items_json` (lista de dicts equipo_id+cantidad)."""
    return json.dumps([{"equipo_id": i.equipo_id, "cantidad": i.cantidad} for i in items])


def desde_items_json(raw) -> list[dict]:
    """Lee `items_json` sea ya-lista (jsonb que psycopg ya deserializó) o string JSON —
    patrón hoy repetido en carritos.py / compartir.py / listas.py, unificado acá."""
    if isinstance(raw, list):
        return raw
    return json.loads(raw or "[]")


def a_tuplas(items: list[SeleccionItem]) -> list[tuple[int, int]]:
    """Proyección a tuplas `(equipo_id, cantidad)` — para los INSERT de listas."""
    return [(i.equipo_id, i.cantidad) for i in items]
