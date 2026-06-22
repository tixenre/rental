"""Tests del ranking de demanda latente de carritos (#280 Fase 2.5).

`_calcular_demanda` es puro (agrega los items de los carritos activos sin tocar
la DB) → se testea sin Postgres. Fija el contrato del ranking: agrupar por
equipo, contar carritos + unidades, y ordenar por presencia y luego unidades.
"""

from routes.carritos import _calcular_demanda


def _carrito(items):
    return {"items": items}


def test_agrupa_por_equipo_cuenta_carritos_y_unidades():
    carritos = [
        _carrito([
            {"equipo_id": 1, "nombre": "FX3", "cantidad": 1},
            {"equipo_id": 2, "nombre": "Trípode", "cantidad": 2},
        ]),
        _carrito([{"equipo_id": 1, "nombre": "FX3", "cantidad": 3}]),
    ]

    ranking = _calcular_demanda(carritos)
    por_id = {d["equipo_id"]: d for d in ranking}

    assert por_id[1]["carritos"] == 2
    assert por_id[1]["unidades"] == 4
    assert por_id[1]["nombre"] == "FX3"
    assert por_id[2]["carritos"] == 1
    assert por_id[2]["unidades"] == 2


def test_ordena_por_presencia_y_luego_unidades():
    carritos = [
        _carrito([{"equipo_id": 10, "nombre": "A", "cantidad": 9}]),
        _carrito([{"equipo_id": 20, "nombre": "B", "cantidad": 1}]),
        _carrito([{"equipo_id": 20, "nombre": "B", "cantidad": 1}]),
    ]

    ranking = _calcular_demanda(carritos)

    # B aparece en 2 carritos → va primero aunque A pida más unidades.
    assert ranking[0]["equipo_id"] == 20
    assert ranking[1]["equipo_id"] == 10


def test_vacio_devuelve_lista_vacia():
    assert _calcular_demanda([]) == []
    assert _calcular_demanda([_carrito([])]) == []
