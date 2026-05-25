"""Tests del formatter canónico de specs (services/spec_render.py).

Confirma que:
- `norm_spec_label` matchea el approach del frontend (lowercase + NFD sin tildes).
- `format_tabla_cell` maneja valor_unidad y escalares.
- `format_tabla_value` aplica row_strategy y prefijos de columna correctamente.
- `render_spec_placeholder` resuelve "", "colKey" y "colKey[i]" para tabla,
  y devuelve el value directo para tipos escalares.
"""

import json

import pytest

pytestmark = pytest.mark.unit

from services.spec_render import (
    format_tabla_cell,
    format_tabla_value,
    norm_spec_label,
    render_spec_placeholder,
    render_spec_value,
)


# ── Unidad prefijo (f/, $) + render_spec_value (display ficha/destacados) ──

def test_rango_prefijo_apertura():
    # f/ es unidad prefijo → "f/2.8", no "2.8 f/".
    assert render_spec_placeholder("[2.8]", "rango", None, None, "", unidad="f/") == "f/2.8"


def test_rango_prefijo_apertura_variable():
    assert render_spec_placeholder("[2.8, 4]", "rango", None, None, "", unidad="f/") == "f/2.8 - 4"


def test_render_spec_value_rango_sufijo():
    assert render_spec_value("[24, 70]", "rango", "mm") == "24 - 70 mm"


def test_render_spec_value_rango_prefijo():
    assert render_spec_value("[2.8]", "rango", "f/") == "f/2.8"


def test_render_spec_value_number_con_unidad():
    assert render_spec_value("82", "number", "mm") == "82 mm"


def test_render_spec_value_enum_tal_cual():
    assert render_spec_value("Full-frame", "enum", None) == "Full-frame"
    assert render_spec_value("E", "enum", None) == "E"


def test_render_spec_value_bool_vacio_si_false():
    assert render_spec_value("false", "bool", None) == ""


COLS_LUMEN = [
    {"key": "lumen", "label": "Flujo", "tipo": "valor_unidad", "prefijo": None},
    {"key": "temp", "label": "Temperatura", "tipo": "valor_unidad", "prefijo": "a"},
]

ROWS_LUMEN = [
    {"lumen": {"valor": 19389, "unidad": "lm"}, "temp": {"valor": 5700, "unidad": "K"}},
    {"lumen": {"valor": 15560, "unidad": "lm"}, "temp": {"valor": 3200, "unidad": "K"}},
]

VAL_LUMEN = json.dumps(ROWS_LUMEN)


def test_norm_spec_label_quita_tildes_y_pasa_a_lowercase():
    assert norm_spec_label("Iluminación") == "iluminacion"
    assert norm_spec_label("  Lens MOUNT  ") == "lens mount"
    assert norm_spec_label("") == ""


def test_format_tabla_cell_valor_unidad():
    assert format_tabla_cell({"valor": 10000, "unidad": "lm"}) == "10000 lm"
    assert format_tabla_cell({"valor": 10000, "unidad": None}) == "10000"
    # Legacy: si valor es None pero hay unidad, devuelve solo la unidad.
    # Edge que no se da en producción (el JSON no incluye celdas vacías).
    assert format_tabla_cell({"valor": None, "unidad": "lm"}) == "lm"


def test_format_tabla_cell_escalar():
    assert format_tabla_cell("4K") == "4K"
    assert format_tabla_cell(42) == "42"
    assert format_tabla_cell(None) == ""
    assert format_tabla_cell("") == ""


def test_format_tabla_value_all_rows_default():
    # row_strategy default = "all". Las 2 filas se rinden separadas por \n.
    out = format_tabla_value(VAL_LUMEN, COLS_LUMEN, None)
    assert out == "19389 lm a 5700 K\n15560 lm a 3200 K"


def test_format_tabla_value_row_strategy_first():
    out = format_tabla_value(VAL_LUMEN, COLS_LUMEN, {"row_strategy": "first"})
    assert out == "19389 lm a 5700 K"


def test_format_tabla_value_row_strategy_last():
    out = format_tabla_value(VAL_LUMEN, COLS_LUMEN, {"row_strategy": "last"})
    assert out == "15560 lm a 3200 K"


def test_format_tabla_value_unidad_fija_en_columna_escalar():
    cols = [
        {"key": "lumen", "label": "Flujo", "tipo": "number", "unidad": "lm"},
        {"key": "temp", "label": "Temperatura", "tipo": "number", "unidad": "K", "prefijo": "a"},
    ]
    rows = [{"lumen": 10000, "temp": 5700}]
    out = format_tabla_value(json.dumps(rows), cols, None)
    assert out == "10000 lm a 5700 K"


def test_format_tabla_value_devuelve_value_original_si_invalido():
    assert format_tabla_value("no es json", COLS_LUMEN, None) == "no es json"
    assert format_tabla_value("{}", COLS_LUMEN, None) == "{}"


def test_render_spec_placeholder_sin_path_tipo_tabla():
    # {spec:Lumen} → render completo con row_strategy aplicada.
    out = render_spec_placeholder(VAL_LUMEN, "tabla", COLS_LUMEN, None, "")
    assert out == "19389 lm a 5700 K\n15560 lm a 3200 K"

    out_first = render_spec_placeholder(VAL_LUMEN, "tabla", COLS_LUMEN, {"row_strategy": "first"}, "")
    assert out_first == "19389 lm a 5700 K"


def test_render_spec_placeholder_sin_path_tipo_escalar():
    # {spec:Montura} para tipo enum/string → devuelve el value tal cual.
    assert render_spec_placeholder("E", "enum", None, None, "") == "E"
    assert render_spec_placeholder("Full Frame", "string", None, None, "") == "Full Frame"


def test_render_spec_placeholder_con_columna():
    # {spec:Lumen.lumen} → fila 0 por default, columna lumen.
    assert render_spec_placeholder(VAL_LUMEN, "tabla", COLS_LUMEN, None, "lumen") == "19389 lm"
    # row_strategy NO aplica cuando hay path explícito.
    assert render_spec_placeholder(
        VAL_LUMEN, "tabla", COLS_LUMEN, {"row_strategy": "last"}, "lumen"
    ) == "19389 lm"


def test_render_spec_placeholder_con_columna_y_indice():
    # {spec:Lumen.lumen[1]} → fila 1, columna lumen.
    assert render_spec_placeholder(VAL_LUMEN, "tabla", COLS_LUMEN, None, "lumen[1]") == "15560 lm"
    assert render_spec_placeholder(VAL_LUMEN, "tabla", COLS_LUMEN, None, "temp[0]") == "5700 K"


def test_render_spec_placeholder_indice_fuera_de_rango():
    assert render_spec_placeholder(VAL_LUMEN, "tabla", COLS_LUMEN, None, "lumen[99]") == ""


# ── Tests del formato por tipo (multi_enum, rango, bool) — refactor 2026-05-22


def test_render_multi_enum_json_array():
    """multi_enum value JSON array → join con ' · '."""
    value = '["RGB", "Tungsten", "Daylight"]'
    out = render_spec_placeholder(value, "multi_enum", None, None, "")
    assert out == "RGB · Tungsten · Daylight"


def test_render_multi_enum_string_legacy():
    """Si el value es string simple (no JSON), devolver tal cual."""
    out = render_spec_placeholder("RGB", "multi_enum", None, None, "")
    assert out == "RGB"


def test_render_multi_enum_con_name_format():
    """name_format se aplica al join."""
    value = '["RGB", "Tungsten"]'
    oc = {"name_format": "Modos: {value}"}
    out = render_spec_placeholder(value, "multi_enum", None, oc, "")
    assert out == "Modos: RGB · Tungsten"


def test_render_rango_min_max():
    value = "[80, 102400]"
    out = render_spec_placeholder(value, "rango", None, None, "")
    assert out == "80 - 102400"


def test_render_rango_con_unidad():
    out = render_spec_placeholder("[80, 102400]", "rango", None, None, "", unidad="ISO")
    assert out == "80 - 102400 ISO"


def test_render_rango_valor_unico():
    out = render_spec_placeholder("[5600]", "rango", None, None, "", unidad="K")
    assert out == "5600 K"


def test_render_bool_true():
    """bool `true` → label proxy ('Sí')."""
    out = render_spec_placeholder("true", "bool", None, None, "")
    assert out == "Sí"


def test_render_bool_false():
    """bool `false` → vacío (para colapsar conectores en el template)."""
    out = render_spec_placeholder("false", "bool", None, None, "")
    assert out == ""


def test_render_number_unchanged():
    """number sigue devolviendo el value como string."""
    out = render_spec_placeholder("19389", "number", None, None, "", unidad="lm")
    assert out == "19389"


def test_render_number_con_name_format_y_unidad():
    """name_format con {value} y {unidad}."""
    oc = {"name_format": "{value} {unidad}"}
    out = render_spec_placeholder("19389", "number", None, oc, "", unidad="lm")
    assert out == "19389 lm"
