"""Tests Fase 6c-i — Render de specs vacías y tipos faltantes.

Verifica:
1. _is_empty_value detecta None / "" / "[]" / "{}"
2. render_spec_value devuelve "" para valores vacíos
3. tabla: render best-effort sin columnas produce texto legible, no JSON
4. wxh / wxhxd: pass-through de strings ya formateados
5. bool false → render vacío
6. multi_enum "[]" → render vacío (via _is_empty_value)
"""

import json
import pytest

pytestmark = pytest.mark.unit

from services.spec_render import (
    _is_empty_value,
    render_spec_value,
    _render_tabla_best_effort,
)


# ── _is_empty_value ──────────────────────────────────────────────────────────


def test_is_empty_none():
    assert _is_empty_value(None) is True


def test_is_empty_empty_string():
    assert _is_empty_value("") is True


def test_is_empty_whitespace():
    assert _is_empty_value("   ") is True


def test_is_empty_json_array_vacio():
    assert _is_empty_value("[]") is True


def test_is_empty_json_obj_vacio():
    assert _is_empty_value("{}") is True


def test_is_empty_value_real():
    assert _is_empty_value("E") is False
    assert _is_empty_value("120") is False
    assert _is_empty_value('[24, 70]') is False


# ── render_spec_value: valores vacíos → "" ───────────────────────────────────


def test_render_empty_string():
    assert render_spec_value("", "string") == ""


def test_render_none():
    assert render_spec_value(None, "number") == ""  # type: ignore[arg-type]


def test_render_json_array_vacio():
    assert render_spec_value("[]", "multi_enum") == ""


def test_render_json_obj_vacio():
    assert render_spec_value("{}", "tabla") == ""


# ── bool false → render vacío ────────────────────────────────────────────────


def test_render_bool_false():
    assert render_spec_value("false", "bool") == ""


def test_render_bool_no():
    assert render_spec_value("no", "bool") == ""


def test_render_bool_true():
    assert render_spec_value("true", "bool") == "Sí"


# ── tabla: render legible, no JSON crudo ────────────────────────────────────


def test_render_tabla_best_effort_simple():
    """Una tabla de una fila con dos celdas → 'v1 · v2'."""
    value = json.dumps([{"Temp": "5600K", "Flux": "19389 lm"}])
    result = _render_tabla_best_effort(value)
    assert "5600K" in result
    assert "19389 lm" in result
    assert result != value  # no es el JSON crudo


def test_render_tabla_via_render_spec_value():
    value = json.dumps([{"Temp": "5600K", "Flux": "19389 lm"}])
    result = render_spec_value(value, "tabla")
    assert "5600K" in result
    assert result != value


def test_render_tabla_multifila():
    value = json.dumps([
        {"col": "Fila 1"},
        {"col": "Fila 2"},
    ])
    result = render_spec_value(value, "tabla")
    assert "Fila 1" in result
    assert "Fila 2" in result


def test_render_tabla_vacia():
    """Tabla vacía "[]" → render vacío."""
    assert render_spec_value("[]", "tabla") == ""


def test_render_tabla_json_invalido():
    """Si el JSON es inválido, best-effort devuelve el value crudo."""
    result = _render_tabla_best_effort("not-json")
    assert result == "not-json"


# ── wxh / wxhxd: strings ya formateados, pass-through ───────────────────────


def test_render_wxh_passthrough():
    """wxh almacenado como '6144×3240 px' → se devuelve tal cual."""
    assert render_spec_value("6144×3240 px", "wxh") == "6144×3240 px"


def test_render_wxhxd_passthrough():
    """wxhxd almacenado como '129.7×84.5×77.8 mm' → se devuelve tal cual."""
    assert render_spec_value("129.7×84.5×77.8 mm", "wxhxd") == "129.7×84.5×77.8 mm"


# ── multi_enum relleno → legible ─────────────────────────────────────────────


def test_render_multi_enum_lista():
    value = json.dumps(["Daylight", "Bicolor"])
    result = render_spec_value(value, "multi_enum")
    assert result == "Daylight · Bicolor"


def test_render_multi_enum_vacio():
    assert render_spec_value("[]", "multi_enum") == ""


# ── rango con unidad ─────────────────────────────────────────────────────────


def test_render_rango_con_unidad():
    value = json.dumps([2500, 7500])
    result = render_spec_value(value, "rango", "K")
    assert result == "2500-7500 K"


def test_render_rango_fijo():
    value = json.dumps([50])
    result = render_spec_value(value, "rango", "mm")
    assert result == "50 mm"


# ── number con unidad ────────────────────────────────────────────────────────


def test_render_number_con_unidad():
    assert render_spec_value("320", "number", "W") == "320 W"


def test_render_number_sin_unidad():
    assert render_spec_value("320", "number") == "320"


# ── Data legacy no-canónica (rango/number crudos) → render igual aplica unidad ──


def test_render_rango_legacy_plano_con_unidad():
    """Rango guardado crudo (no JSON): "24-70" → "24-70 mm"."""
    assert render_spec_value("24-70", "rango", "mm") == "24-70 mm"


def test_render_rango_legacy_fijo_prefijo():
    """Apertura legacy "2.8" (rango, unidad f/) → "f/2.8"."""
    assert render_spec_value("2.8", "rango", "f/") == "f/2.8"


def test_render_rango_legacy_grados():
    assert render_spec_value("34.3-84.1", "rango", "°") == "34.3-84.1°"


def test_render_number_unidad_pegada_no_duplica():
    """Peso legacy con unidad pegada "1020 g" → "1020 g" (no "1020 g g")."""
    assert render_spec_value("1020 g", "number", "g") == "1020 g"
