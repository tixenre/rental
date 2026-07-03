"""Regresión: `_enrich_items` (carritos activos) tiene que incluir el precio
EFECTIVO de un combo en el `monto_estimado`, no descartarlo.

Bug (auditoría de plata): `equipos.precio_jornada` es NULL para un `tipo='combo'`
(el precio de un combo se deriva de sus componentes vía
`services.precios.precio_jornada_efectivo` — no vive en esa columna). El código
viejo leía la columna cruda, la coercía a 0 y el combo quedaba afuera del
`monto_estimado`/`pipeline_ars` del dashboard admin de `/admin/carritos` — el
dueño veía menos plata "en camino" de la que había en carritos activos con combos.
"""

import pytest

pytestmark = pytest.mark.unit


class _FakeCursor:
    def __init__(self, one=None, many=None):
        self._one = one
        self._many = many or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _FakeConn:
    """Resuelve las queries que dispara `_enrich_items` → `precio_jornada_efectivo`
    → `precio_combo` (cadena real, sin mockear el resolutor): nombre del equipo,
    fila base (`precio_jornada`/`tipo`) y — solo para combos — sus componentes.
    """

    def __init__(self, equipos: dict, componentes: dict):
        self._equipos = equipos
        self._componentes = componentes

    def execute(self, sql, params=None):
        equipo_id = params[0] if params else None
        if "kit_componentes" in sql:
            return _FakeCursor(many=self._componentes.get(equipo_id, []))
        eq = self._equipos.get(equipo_id)
        if "e.nombre" in sql:
            return _FakeCursor(one={"nombre": eq["nombre"]} if eq else None)
        # SELECT precio_jornada, tipo FROM equipos ... (precio_jornada_efectivo)
        if eq is None:
            return _FakeCursor(one=None)
        return _FakeCursor(one={"precio_jornada": eq["precio_jornada"], "tipo": eq["tipo"]})

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _item(equipo_id, cantidad):
    class _It:
        pass

    it = _It()
    it.equipo_id = equipo_id
    it.cantidad = cantidad
    return it


def test_enrich_items_incluye_precio_derivado_de_un_combo(monkeypatch):
    from services.carrito import activos

    equipos = {
        1: {"nombre": "Trípode", "precio_jornada": 1000, "tipo": "simple"},
        # Combo: `precio_jornada` NULL en la columna cruda — se deriva de sus
        # componentes (2000 × 1 unidad, sin descuento de línea).
        2: {"nombre": "Combo Filmmaker", "precio_jornada": None, "tipo": "combo"},
    }
    componentes = {
        2: [{"precio_jornada": 2000, "cantidad": 1, "descuento_pct": 0}],
    }
    monkeypatch.setattr(activos, "get_db", lambda: _FakeConn(equipos, componentes))

    items = [_item(1, 1), _item(2, 1)]
    enriched, monto_estimado = activos._enrich_items(items, None, None)

    nombres = {e["equipo_id"]: e["nombre"] for e in enriched}
    assert nombres == {1: "Trípode", 2: "Combo Filmmaker"}
    # Antes del fix: el combo aportaba $0 (precio_jornada crudo NULL → 0) y se
    # descartaba del estimado → hubiera dado 1000. Con el fix: 1000 (simple) +
    # 2000 (combo derivado de sus componentes) = 3000.
    assert monto_estimado == 3000


def test_enrich_items_carrito_solo_con_combo_no_da_cero(monkeypatch):
    from services.carrito import activos

    equipos = {5: {"nombre": "Combo Streaming", "precio_jornada": None, "tipo": "combo"}}
    componentes = {
        5: [
            {"precio_jornada": 1500, "cantidad": 1, "descuento_pct": 0},
            {"precio_jornada": 500, "cantidad": 2, "descuento_pct": 10},
        ],
    }
    monkeypatch.setattr(activos, "get_db", lambda: _FakeConn(equipos, componentes))

    _, monto_estimado = activos._enrich_items([_item(5, 1)], None, None)

    # 1500×1 + 500×2×0.9 = 1500 + 900 = 2400. Antes del fix esto daba 0.
    assert monto_estimado == 2400
