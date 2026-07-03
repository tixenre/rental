"""specs_search_expr — forma del SQL generado (#1163 F4). Sin DB, solo
confirma que la expresión sigue teniendo la forma esperada (tablas/columnas
referenciadas). El comportamiento real contra datos se prueba en
test_specs_search_source_db.py.
"""
import pytest

from services.specs.queries.search_source import specs_search_expr

pytestmark = pytest.mark.unit


def test_referencia_las_tablas_correctas():
    expr = specs_search_expr()
    assert "equipo_specs" in expr
    assert "spec_definitions" in expr
    assert "spec_value_aliases" in expr


def test_usa_el_alias_de_tabla_pasado():
    assert "x.id" in specs_search_expr("x")
    assert "e.id" in specs_search_expr("e")
    assert "e.id" in specs_search_expr()  # default


def test_es_null_safe_via_string_agg():
    # string_agg sin filas devuelve NULL (no ''), a propósito — igual que
    # _FICHA_EXPR. No debe forzar coalesce a nivel de expresión completa.
    assert specs_search_expr().strip().startswith("(SELECT string_agg")
