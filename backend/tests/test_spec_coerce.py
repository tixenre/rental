"""Tests de Fase 2 — coerción de valores crudos al tipo canónico del registry.

Cubre services/specs/commands/coerce.py:
- _coerce_number: extrae primer número, descarta unidades
- _coerce_bool: yes/si/sí/true/1 → "true", no/false/0 → "false"
- _coerce_enum: match case-insensitive contra enum_options
- _coerce_rango: "24-70mm" → "[24, 70]", "50mm" → "[50]", "2.8" → "[2.8]"
- _coerce_multi_enum: CSV / slash / JSON array
- coerce_and_serialize: dispatch por tipo
- derive_lumens_from_lux: fórmula fotométrica
"""

import json
import math
import pytest

pytestmark = pytest.mark.unit

from services.specs.commands.coerce import (
    coerce_and_serialize,
    derive_lumens_from_lux,
    _coerce_number,
    _coerce_bool,
    _coerce_enum,
    _coerce_rango,
    _coerce_multi_enum,
)


# ── _coerce_number ───────────────────────────────────────────────────────────


def test_coerce_number_con_unidad_gramos():
    assert _coerce_number("890 g") == "890"


def test_coerce_number_con_unidad_vatios():
    assert _coerce_number("24W") == "24"


def test_coerce_number_con_unidad_mm():
    assert _coerce_number("50mm") == "50"


def test_coerce_number_decimal():
    assert _coerce_number("2.8") == "2.8"


def test_coerce_number_decimal_coma():
    assert _coerce_number("1,4") == "1.4"


def test_coerce_number_solo_numero():
    assert _coerce_number("120") == "120"


def test_coerce_number_texto_prefijo():
    assert _coerce_number("Approx. 500 g") == "500"


def test_coerce_number_texto_sin_numero():
    assert _coerce_number("N/A") is None


def test_coerce_number_entero_preservado():
    # 1200.0 → "1200" (no "1200.0")
    assert _coerce_number("1200") == "1200"


# ── _coerce_bool ─────────────────────────────────────────────────────────────


def test_coerce_bool_yes():
    assert _coerce_bool("Yes") == "true"


def test_coerce_bool_si_sin_tilde():
    assert _coerce_bool("Si") == "true"


def test_coerce_bool_si_con_tilde():
    assert _coerce_bool("Sí") == "true"


def test_coerce_bool_true():
    assert _coerce_bool("true") == "true"


def test_coerce_bool_1():
    assert _coerce_bool("1") == "true"


def test_coerce_bool_no():
    assert _coerce_bool("No") == "false"


def test_coerce_bool_false():
    assert _coerce_bool("false") == "false"


def test_coerce_bool_0():
    assert _coerce_bool("0") == "false"


def test_coerce_bool_case_insensitive():
    assert _coerce_bool("YES") == "true"
    assert _coerce_bool("NO") == "false"
    assert _coerce_bool("TRUE") == "true"
    assert _coerce_bool("FALSE") == "false"


def test_coerce_bool_desconocido():
    assert _coerce_bool("maybe") is None
    assert _coerce_bool("enabled partially") is None


def test_coerce_bool_enabled():
    assert _coerce_bool("enabled") == "true"


def test_coerce_bool_disabled():
    assert _coerce_bool("disabled") == "false"


# ── _coerce_enum ─────────────────────────────────────────────────────────────


def test_coerce_enum_match_exacto():
    opts = ["E-Mount", "F-Mount", "RF"]
    assert _coerce_enum("E-Mount", opts) == "E-Mount"


def test_coerce_enum_match_case_insensitive():
    opts = ["E-Mount", "F-Mount", "RF"]
    assert _coerce_enum("e-mount", opts) == "E-Mount"
    assert _coerce_enum("E-MOUNT", opts) == "E-Mount"


def test_coerce_enum_sin_match():
    opts = ["E-Mount", "F-Mount"]
    assert _coerce_enum("PL-Mount", opts) is None


def test_coerce_enum_lista_vacia():
    assert _coerce_enum("E-Mount", []) is None


# ── _coerce_rango ─────────────────────────────────────────────────────────────


def test_coerce_rango_zoom_mm():
    result = _coerce_rango("24-70mm")
    assert json.loads(result) == [24, 70]


def test_coerce_rango_prime_mm():
    result = _coerce_rango("50mm")
    assert json.loads(result) == [50]


def test_coerce_rango_apertura_simple():
    result = _coerce_rango("2.8")
    assert json.loads(result) == [2.8]


def test_coerce_rango_apertura_slash():
    result = _coerce_rango("f/2.8")
    assert json.loads(result) == [2.8]


def test_coerce_rango_apertura_variable():
    result = _coerce_rango("f/2.8-4")
    assert json.loads(result) == [2.8, 4.0]


def test_coerce_rango_temperatura_k():
    result = _coerce_rango("3200-5600")
    assert json.loads(result) == [3200, 5600]


def test_coerce_rango_texto_sin_numero():
    assert _coerce_rango("N/A") is None


def test_coerce_rango_decimal_preservado():
    result = _coerce_rango("1.4")
    assert json.loads(result) == [1.4]


def test_coerce_rango_entero_no_decimal():
    result = _coerce_rango("24-70mm")
    parsed = json.loads(result)
    assert all(isinstance(v, int) for v in parsed), "enteros no deben tener .0"


# ── _coerce_multi_enum ────────────────────────────────────────────────────────


def test_coerce_multi_enum_csv():
    opts = ["USB-C", "HDMI", "SDI", "XLR"]
    result = _coerce_multi_enum("USB-C, HDMI", opts)
    assert json.loads(result) == ["USB-C", "HDMI"]


def test_coerce_multi_enum_slash():
    opts = ["USB-C", "HDMI", "SDI"]
    result = _coerce_multi_enum("USB-C/HDMI", opts)
    assert json.loads(result) == ["USB-C", "HDMI"]


def test_coerce_multi_enum_json_array():
    opts = ["USB-C", "HDMI"]
    result = _coerce_multi_enum('["USB-C", "HDMI"]', opts)
    assert json.loads(result) == ["USB-C", "HDMI"]


def test_coerce_multi_enum_sin_opts_usa_raw():
    result = _coerce_multi_enum("AC, DC, Battery", [])
    assert json.loads(result) == ["AC", "DC", "Battery"]


def test_coerce_multi_enum_valor_solo():
    opts = ["AC", "DC"]
    result = _coerce_multi_enum("AC", opts)
    assert json.loads(result) == ["AC"]


def test_coerce_multi_enum_vacio():
    assert _coerce_multi_enum("", []) is None


# ── coerce_and_serialize (dispatch) ──────────────────────────────────────────


def test_dispatch_number():
    result = coerce_and_serialize("890 g", "number")
    assert result == "890"


def test_dispatch_bool():
    assert coerce_and_serialize("Yes", "bool") == "true"
    assert coerce_and_serialize("No", "bool") == "false"


def test_dispatch_enum():
    opts = json.dumps(["E-Mount", "F-Mount"])
    assert coerce_and_serialize("e-mount", "enum", enum_options_json=opts) == "E-Mount"


def test_dispatch_rango():
    result = coerce_and_serialize("24-70mm", "rango")
    assert json.loads(result) == [24, 70]


def test_dispatch_multi_enum():
    opts = json.dumps(["USB-C", "HDMI"])
    result = coerce_and_serialize("USB-C, HDMI", "multi_enum", enum_options_json=opts)
    assert json.loads(result) == ["USB-C", "HDMI"]


def test_dispatch_string_passthrough():
    assert coerce_and_serialize("E-Mount", "string") == "E-Mount"


def test_dispatch_none_returns_none():
    assert coerce_and_serialize(None, "number") is None


def test_dispatch_empty_returns_none():
    assert coerce_and_serialize("", "number") is None


def test_dispatch_falla_devuelve_none():
    # number sin ningún dígito → None, no excepción
    assert coerce_and_serialize("sin números aquí!", "number") is None


# ── derive_lumens_from_lux ────────────────────────────────────────────────────


def test_derive_lumens_angulo_120():
    # Haz de 120°: cos(60°) = 0.5, factor = 2π×(1−0.5) = π ≈ 3.1416
    # Para 1000 lux → ≈ 3142 lm
    lm = derive_lumens_from_lux(1000, 120)
    assert lm is not None
    expected = round(1000 * 2 * math.pi * (1 - math.cos(math.radians(60))))
    assert lm == expected


def test_derive_lumens_angulo_60():
    # Haz de 60°: cos(30°) ≈ 0.866, factor = 2π×(1−0.866) ≈ 0.842
    lm = derive_lumens_from_lux(1000, 60)
    assert lm is not None
    expected = round(1000 * 2 * math.pi * (1 - math.cos(math.radians(30))))
    assert lm == expected


def test_derive_lumens_positivo():
    lm = derive_lumens_from_lux(500, 90)
    assert lm is not None and lm >= 1


def test_derive_lumens_lux_cero():
    assert derive_lumens_from_lux(0, 90) is None


def test_derive_lumens_angulo_cero():
    assert derive_lumens_from_lux(1000, 0) is None


def test_derive_lumens_angulo_invalido():
    assert derive_lumens_from_lux(1000, 361) is None


def test_derive_lumens_angulo_360_limite():
    # 360° = hemisferio completo, válido
    lm = derive_lumens_from_lux(1000, 360)
    assert lm is not None and lm >= 1


def test_derive_lumens_retorna_entero():
    lm = derive_lumens_from_lux(1234, 90)
    assert isinstance(lm, int)
