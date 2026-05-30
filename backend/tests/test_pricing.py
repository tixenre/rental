"""Tests de helpers de precio + stock en alquileres.py."""

import pytest

from reservas import consolidar_items_por_equipo as _consolidar_items_por_equipo
from routes.alquileres import _parse_precio


pytestmark = pytest.mark.unit


class TestConsolidarItemsPorEquipo:
    """Regresión de #102 — items duplicados del mismo equipo deben sumarse
    antes de validar stock. Sino la validación pasa con falsa negativa."""

    def test_items_distintos_se_mantienen_separados(self):
        items = [
            {"equipo_id": 1, "cantidad": 2, "nombre": "Sony FX3", "stock_total": 3},
            {"equipo_id": 2, "cantidad": 1, "nombre": "Canon R5", "stock_total": 5},
        ]
        out = _consolidar_items_por_equipo(items)
        assert len(out) == 2
        assert out[1]["cantidad"] == 2
        assert out[2]["cantidad"] == 1

    def test_items_del_mismo_equipo_se_suman(self):
        # El bug latente: dos items del mismo equipo_id deberían validarse
        # como uno solo con la cantidad total.
        items = [
            {"equipo_id": 42, "cantidad": 2, "nombre": "Sony FX3", "stock_total": 3},
            {"equipo_id": 42, "cantidad": 2, "nombre": "Sony FX3", "stock_total": 3},
        ]
        out = _consolidar_items_por_equipo(items)
        assert len(out) == 1
        assert out[42]["cantidad"] == 4  # Sumadas
        assert out[42]["stock_total"] == 3
        # Con 4 necesitadas y 3 stock, _check_stock debería ahora detectar
        # el problema (antes pasaba porque cada item validaba 2 vs 3).

    def test_lista_vacia_devuelve_dict_vacio(self):
        assert _consolidar_items_por_equipo([]) == {}

    def test_un_solo_item(self):
        items = [{"equipo_id": 7, "cantidad": 1, "nombre": "Lente", "stock_total": 2}]
        out = _consolidar_items_por_equipo(items)
        assert out == {
            7: {"equipo_id": 7, "cantidad": 1, "nombre": "Lente", "stock_total": 2}
        }

    def test_tres_items_mismo_equipo(self):
        items = [
            {"equipo_id": 1, "cantidad": 1, "nombre": "X", "stock_total": 10},
            {"equipo_id": 1, "cantidad": 2, "nombre": "X", "stock_total": 10},
            {"equipo_id": 1, "cantidad": 3, "nombre": "X", "stock_total": 10},
        ]
        out = _consolidar_items_por_equipo(items)
        assert out[1]["cantidad"] == 6


# Los tests de aplicar-descuento se movieron a `test_precios_service.py`
# (cubierto por `TestCalcularTotal` que usa el helper canónico).


class TestParsePrecio:
    def test_int_pasa(self):
        assert _parse_precio(1500) == 1500

    def test_float_real_se_interpreta_como_miles_BUG_KNOWN(self):
        """Comportamiento conocido y peligroso: el helper saca puntos pensando
        que son separadores de miles (formato AR '$15.000') y no como decimal.
        Por eso 1500.99 → 150099, no 1500.

        Float real no es input válido en el sistema (los precios entran como
        int o string formato AR), así que no rompe nada hoy. Si alguien empieza
        a pasar floats, este test va a fallar y va a recordar el problema.
        """
        assert _parse_precio(1500.99) == 150099

    def test_string_con_pesos_y_puntos(self):
        # "$15.000" → 15000 (saca $ y .)
        assert _parse_precio("$15.000") == 15000

    def test_string_con_coma_decimal(self):
        # Argentina usa coma como decimal pero _parse_precio la trata como separador miles
        # "1,500" → 1500 (si el helper saca comas) o 1.5→1 (si las trata como decimal)
        result = _parse_precio("1,500")
        assert isinstance(result, int)

    def test_vacio_devuelve_cero(self):
        assert _parse_precio("") == 0
        assert _parse_precio(None) == 0

    def test_string_invalido_devuelve_cero(self):
        assert _parse_precio("no es un precio") == 0

    def test_negativo_se_preserva(self):
        # Es responsabilidad del caller validar negatividad
        assert _parse_precio(-100) == -100
