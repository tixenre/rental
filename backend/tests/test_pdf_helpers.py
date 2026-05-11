"""Tests de helpers de pdf.py — formato de fechas, montos, nombres."""

import pytest

from pdf import (
    _es_month,
    _fmt_ars,
    _fmt_date_long,
    _fmt_date_short,
    _nombre_para_pdf,
    _parse_valor,
)


pytestmark = pytest.mark.unit


class TestEsMonth:
    def test_traduce_meses_individuales(self):
        assert "enero" in _es_month("5 de January de 2026")
        assert "marzo" in _es_month("March 2026")
        assert "diciembre" in _es_month("31 December")

    def test_no_modifica_si_no_hay_mes_en_ingles(self):
        assert _es_month("ya está en español") == "ya está en español"

    def test_traduce_todos_los_meses(self):
        meses_en = ["January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December"]
        meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        for en, es in zip(meses_en, meses_es):
            assert _es_month(en) == es, f"{en} debería traducirse a {es}"


class TestFmtArs:
    def test_formato_basico(self):
        assert _fmt_ars(1234) == "$1.234"
        assert _fmt_ars(1234567) == "$1.234.567"

    def test_cero_con_dash_por_default(self):
        assert _fmt_ars(0) == "—"

    def test_cero_sin_dash_devuelve_pesos(self):
        assert _fmt_ars(0, zero_dash=False) == "$0"

    def test_none_devuelve_dash(self):
        assert _fmt_ars(None) == "—"

    def test_acepta_string_numerico(self):
        # _fmt_ars usa int(float(n or 0)) — un string numérico válido funciona
        assert _fmt_ars("1500") == "$1.500"

    def test_string_no_numerico_no_rompe(self):
        # Fallback: devuelve el string crudo o "—"
        result = _fmt_ars("no es número")
        assert isinstance(result, str)


class TestFmtDate:
    def test_short_iso(self):
        assert _fmt_date_short("2026-05-11") == "11/05/2026"

    def test_short_vacio_devuelve_dash(self):
        assert _fmt_date_short("") == "—"
        assert _fmt_date_short(None) == "—"

    def test_long_traduce_mes(self):
        result = _fmt_date_long("2026-05-11")
        assert "mayo" in result
        assert "2026" in result

    def test_invalid_no_rompe(self):
        # Si no es ISO válida, devuelve el string crudo
        result = _fmt_date_short("not-a-date")
        assert isinstance(result, str)


class TestNombreParaPdf:
    def test_publico_corto_por_default(self):
        item = {"nombre_publico": "Sony FX3", "nombre_publico_largo": "Sony FX3 Cuerpo Full-Frame", "nombre": "fx3", "marca": "Sony"}
        assert _nombre_para_pdf(item) == "Sony FX3"

    def test_largo_si_formal(self):
        item = {"nombre_publico": "Sony FX3", "nombre_publico_largo": "Sony FX3 Cuerpo Full-Frame", "nombre": "fx3", "marca": "Sony"}
        assert _nombre_para_pdf(item, formal=True) == "Sony FX3 Cuerpo Full-Frame"

    def test_fallback_a_corto_si_no_hay_largo(self):
        item = {"nombre_publico": "Sony FX3", "nombre_publico_largo": "", "nombre": "fx3", "marca": "Sony"}
        assert _nombre_para_pdf(item, formal=True) == "Sony FX3"

    def test_fallback_marca_nombre_si_no_hay_publico(self):
        item = {"nombre_publico": "", "nombre_publico_largo": "", "nombre": "fx3", "marca": "Sony"}
        assert _nombre_para_pdf(item) == "Sony fx3"

    def test_no_duplica_marca_si_ya_esta_en_nombre(self):
        item = {"nombre_publico": "", "nombre_publico_largo": "", "nombre": "Sony FX3", "marca": "Sony"}
        # marca ya está en nombre → no la repite
        assert _nombre_para_pdf(item) == "Sony FX3"

    def test_dash_si_todo_vacio(self):
        item = {"nombre_publico": "", "nombre_publico_largo": "", "nombre": "", "marca": ""}
        assert _nombre_para_pdf(item) == "—"


class TestParseValor:
    def test_int_devuelve_int(self):
        assert _parse_valor(1500) == 1500

    def test_string_con_signo_pesos(self):
        # Si la implementación remueve $ y puntos: '$1.500' → 1500
        result = _parse_valor("$1.500")
        assert result == 1500

    def test_vacio_o_none_devuelve_cero(self):
        assert _parse_valor("") == 0
        assert _parse_valor(None) == 0
