"""Tests del observatorio de specs (sin tocar DB).

Cubre las funciones puras del módulo `routes/specs_observatorio.py`:
- `_extract_specs_from_raw`: parser del raw_json cacheado.
- `_source_from_url`: clasificación del origen del scrape.
"""

import json

import pytest

pytestmark = pytest.mark.unit

# Importar las funciones puras sin disparar el router (FastAPI/pydantic).
# Hacemos un import "lazy" por path para no requerir que FastAPI esté
# instalado en el sandbox de tests unitarios.
import importlib.util
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = BACKEND_ROOT / "routes" / "specs_observatorio.py"


def _load_module():
    """Carga el módulo. Si las deps de FastAPI/pydantic no están, skipea."""
    try:
        spec = importlib.util.spec_from_file_location("specs_obs_mod", MODULE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except ModuleNotFoundError as e:
        pytest.skip(f"deps no instaladas: {e}")


def test_extract_specs_from_raw_json_normal():
    mod = _load_module()
    raw = json.dumps({
        "marca": "Sony",
        "modelo": "FX3",
        "specs": [
            {"label": "Lens mount", "value": "E"},
            {"label": "Formato", "value": "Full-frame"},
            {"label": "Peso", "value": "640 g"},
        ],
    })
    out = mod._extract_specs_from_raw(raw)
    assert len(out) == 3
    assert out[0] == {"label": "Lens mount", "value": "E"}


def test_extract_specs_from_raw_descarta_label_o_value_vacio():
    mod = _load_module()
    raw = json.dumps({
        "specs": [
            {"label": "Lens mount", "value": "E"},
            {"label": "", "value": "X"},          # label vacío
            {"label": "Peso", "value": ""},       # value vacío
            {"label": "Foo", "value": None},      # value None
            {"value": "huérfano"},                # sin label
        ],
    })
    out = mod._extract_specs_from_raw(raw)
    assert len(out) == 1
    assert out[0]["label"] == "Lens mount"


def test_extract_specs_from_raw_json_corrupto():
    mod = _load_module()
    assert mod._extract_specs_from_raw("not json") == []
    assert mod._extract_specs_from_raw('{"specs": "not a list"}') == []
    assert mod._extract_specs_from_raw('{}') == []


def test_source_from_url():
    mod = _load_module()
    assert mod._source_from_url("https://www.bhphotovideo.com/c/product/foo") == "bh"
    assert mod._source_from_url("https://bh.com/x") == "bh"
    assert mod._source_from_url("https://www.adorama.com/foo.html") == "adorama"
    assert mod._source_from_url("https://manufacturer.com/page") == "otro"
    assert mod._source_from_url("") is None
    assert mod._source_from_url(None) is None
