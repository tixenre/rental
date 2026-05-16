"""Tests del normalizer/validator de multi_enum.

Cubre el caso de canonización a JSON array (commit f3a5c7d9e1b6):
- CSV legacy se convierte a JSON.
- JSON array se conserva.
- Valores fuera de enum_options se rechazan.
- Dedup preservando orden.
- Valor vacío devuelve `[]` (que el caller usa para skip insert).
"""

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

BACKEND_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = BACKEND_ROOT / "routes" / "specs.py"


def _load_module():
    try:
        spec = importlib.util.spec_from_file_location("routes_specs_mod", MODULE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except ModuleNotFoundError as e:
        pytest.skip(f"deps no instaladas: {e}")


def test_csv_legacy_se_normaliza_a_json():
    mod = _load_module()
    out = mod._validate_multi_enum_value(
        "HDMI 2.0, SDI 12G", ["HDMI 1.4", "HDMI 2.0", "SDI 12G"], "Conexión",
    )
    assert out == '["HDMI 2.0", "SDI 12G"]'


def test_json_array_se_conserva_normalizado():
    mod = _load_module()
    out = mod._validate_multi_enum_value(
        '["HDMI 2.0", "SDI 12G"]', ["HDMI 2.0", "SDI 12G"], "Conexión",
    )
    # JSON valido viene re-serializado canónico (sin espacios extra).
    import json
    assert json.loads(out) == ["HDMI 2.0", "SDI 12G"]


def test_dedup_preservando_orden():
    mod = _load_module()
    out = mod._validate_multi_enum_value(
        "HDMI 2.0, SDI 12G, HDMI 2.0",
        ["HDMI 2.0", "SDI 12G"],
        "Conexión",
    )
    import json
    assert json.loads(out) == ["HDMI 2.0", "SDI 12G"]


def test_valor_vacio_devuelve_array_vacio():
    mod = _load_module()
    assert mod._validate_multi_enum_value("", ["X"], "Label") == "[]"
    assert mod._validate_multi_enum_value("   ", ["X"], "Label") == "[]"


def test_rechaza_value_fuera_de_enum_options():
    mod = _load_module()
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        mod._validate_multi_enum_value(
            "HDMI 2.0, USB-C", ["HDMI 1.4", "HDMI 2.0"], "Conexión",
        )
    assert "USB-C" in str(ei.value.detail)


def test_acepta_cualquier_valor_si_enum_options_vacio():
    mod = _load_module()
    # Caso de spec sin enum_options declaradas — aceptamos pero canonizamos.
    import json
    out = mod._validate_multi_enum_value(
        "Algo, Otro", [], "Spec sin opciones",
    )
    assert json.loads(out) == ["Algo", "Otro"]


def test_rechaza_json_no_array():
    mod = _load_module()
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        mod._validate_multi_enum_value(
            '{"key": "val"}', ["X"], "Label",
        )


def test_rechaza_json_invalido():
    mod = _load_module()
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        mod._validate_multi_enum_value(
            '[invalid json', ["X"], "Label",
        )
