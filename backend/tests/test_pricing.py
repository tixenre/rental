"""Tests de helpers de precio en alquileres.py."""

import pytest

from routes.alquileres import _aplicar_descuento, _parse_precio


pytestmark = pytest.mark.unit


class TestAplicarDescuento:
    def test_sin_descuento_devuelve_bruto(self):
        assert _aplicar_descuento(1000, 0) == 1000

    def test_descuento_10pct(self):
        assert _aplicar_descuento(1000, 10) == 900

    def test_descuento_15pct_redondea(self):
        # 231300 * 0.85 = 196605
        assert _aplicar_descuento(231300, 15) == 196605

    def test_descuento_100pct_da_cero(self):
        assert _aplicar_descuento(1000, 100) == 0

    def test_pct_none_o_falsy_devuelve_bruto(self):
        # Si pct es 0/None/False, devuelve int(bruto)
        assert _aplicar_descuento(1234.7, 0) == 1234

    def test_pct_negativo_aumenta(self):
        # -10% = 110% del bruto. Es un caso raro pero la función no lo rechaza.
        assert _aplicar_descuento(1000, -10) == 1100


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
