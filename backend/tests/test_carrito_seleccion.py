"""Unit tests de la selección canónica del carrito (`services.carrito.seleccion`).

No tocan la BD: un `conn` falso responde el único SELECT (equipos existentes), así el
test corre en el CI normal (sin Postgres). Cubre dedup / clamp / filtro / cap / orden +
las proyecciones (items_json, tuplas).
"""
import json

from services.carrito import (
    CANTIDAD_MAX,
    MAX_ITEMS,
    SeleccionItem,
    a_items_json,
    a_tuplas,
    desde_items_json,
    normalizar_seleccion,
)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    """Responde `SELECT id FROM equipos WHERE id = ANY(%s)` con los ids existentes."""

    def __init__(self, existentes):
        self._ex = set(existentes)

    def execute(self, _sql, params=None):
        ids = list(params[0]) if params else []
        return _FakeCursor([{"id": i} for i in ids if i in self._ex])


def _it(equipo_id, cantidad=1):
    return SeleccionItem(equipo_id=equipo_id, cantidad=cantidad)


def test_dedup_ultima_cantidad_gana():
    out = normalizar_seleccion(_FakeConn([1]), [_it(1, 2), _it(1, 5)])
    assert out == [SeleccionItem(equipo_id=1, cantidad=5)]


def test_clamp_cantidad():
    out = normalizar_seleccion(_FakeConn([1, 2, 3]), [_it(1, 999), _it(2, 0), _it(3, -4)])
    assert {i.equipo_id: i.cantidad for i in out} == {1: CANTIDAD_MAX, 2: 1, 3: 1}


def test_filtra_inexistentes():
    out = normalizar_seleccion(_FakeConn([1]), [_it(1), _it(2)])
    assert [i.equipo_id for i in out] == [1]


def test_cap_max_items():
    n = MAX_ITEMS + 50
    out = normalizar_seleccion(_FakeConn(range(1, n + 1)), [_it(i) for i in range(1, n + 1)])
    assert len(out) == MAX_ITEMS


def test_preserva_orden():
    out = normalizar_seleccion(_FakeConn([3, 1, 2]), [_it(3), _it(1), _it(2)])
    assert [i.equipo_id for i in out] == [3, 1, 2]


def test_vacio():
    assert normalizar_seleccion(_FakeConn([]), []) == []


def test_acepta_dicts():
    out = normalizar_seleccion(_FakeConn([1]), [{"equipo_id": 1, "cantidad": 3}])
    assert out == [SeleccionItem(equipo_id=1, cantidad=3)]


def test_proyecciones():
    items = [SeleccionItem(equipo_id=1, cantidad=2), SeleccionItem(equipo_id=5, cantidad=1)]
    assert a_tuplas(items) == [(1, 2), (5, 1)]
    assert json.loads(a_items_json(items)) == [
        {"equipo_id": 1, "cantidad": 2},
        {"equipo_id": 5, "cantidad": 1},
    ]
    assert desde_items_json('[{"equipo_id": 1, "cantidad": 2}]') == [{"equipo_id": 1, "cantidad": 2}]
    assert desde_items_json([{"equipo_id": 1, "cantidad": 2}]) == [{"equipo_id": 1, "cantidad": 2}]
