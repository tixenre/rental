"""Regresión: editar fecha_compra daba 500 (PATCH /equipos/{id}).

`equipos.fecha_compra` es DATE, pero el front (MonthYearPicker) manda "YYYY-MM"
(mes/año, issue #109). Postgres no castea "YYYY-MM" a DATE → 500. El handler
ahora normaliza al día 1 vía `_normalize_fecha_compra`.
"""

import pytest

pytestmark = pytest.mark.unit

from routes.equipos import _normalize_fecha_compra


def test_year_month_se_completa_a_dia_1():
    # El caso que rompía: "2024-03" → "2024-03-01" (DATE válido).
    assert _normalize_fecha_compra("2024-03") == "2024-03-01"
    assert _normalize_fecha_compra("2024-12") == "2024-12-01"


def test_fecha_completa_se_deja_igual():
    assert _normalize_fecha_compra("2024-03-15") == "2024-03-15"


def test_vacio_o_none_es_none():
    assert _normalize_fecha_compra("") is None
    assert _normalize_fecha_compra(None) is None
    assert _normalize_fecha_compra("   ") is None
