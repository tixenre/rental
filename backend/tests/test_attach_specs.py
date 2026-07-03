"""Tests de attach_specs_destacados y attach_specs_estructuradas.

El query (SQL, dedup por equipo_id+spec_def_id) vive en
`services.specs.queries.equipo_specs.get_equipo_specs_rows` — testeado
en `test_specs_equipo_specs_model.py`. Acá se testea la POLÍTICA DE
DISPLAY que cada caller aplica sobre esos rows ya resueltos: qué se omite,
qué gana un empate, cómo se renderiza un bool — que sí difiere
legítimamente por audiencia (ficha pública vs. quick facts de card).
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

for _mod in ("psycopg2", "psycopg2.extras", "psycopg2.pool"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from database import attach_specs_destacados, attach_specs_estructuradas


def _row(equipo_id, spec_key, label, tipo, value, prioridad=100,
         unidad=None, en_card=False, en_filtros=False, destacado=None):
    return {
        "equipo_id": equipo_id, "spec_key": spec_key, "label": label,
        "tipo": tipo, "unidad": unidad, "value": value,
        "prioridad": prioridad, "en_card": en_card, "en_filtros": en_filtros,
        "destacado": destacado if destacado is not None else en_card,
    }


def _mock_rows(rows_by_equipo):
    """Patchea get_equipo_specs_rows en los dos módulos donde se importa
    (lazy, dentro de cada función) — mismo patrón que el resto de la
    suite para imports diferidos (ver CLAUDE.md de services/specs)."""
    return patch("services.specs.get_equipo_specs_rows", return_value=rows_by_equipo)


# ── attach_specs_destacados ──────────────────────────────────────────────────


def test_destacados_solo_en_card():
    rows = {1: [
        _row(1, "focal", "Focal", "number", "50", en_card=True),
        _row(1, "peso_g", "Peso", "number", "300", en_card=False),
    ]}
    with _mock_rows(rows):
        result = attach_specs_destacados(MagicMock(), [{"id": 1}])
    labels = [d["label"] for d in result[0]["specs_destacados"]]
    assert labels == ["Focal"]


def test_destacados_bool_true_se_muestra_sin_value():
    rows = {1: [_row(1, "macro", "Macro", "bool", "sí", en_card=True)]}
    with _mock_rows(rows):
        result = attach_specs_destacados(MagicMock(), [{"id": 1}])
    destacados = result[0]["specs_destacados"]
    assert destacados == [{"label": "Macro", "value": ""}]


def test_destacados_bool_false_se_omite():
    """Una spec 'Macro: No' no aporta como quick fact en la card."""
    rows = {1: [_row(1, "macro", "Macro", "bool", "no", en_card=True)]}
    with _mock_rows(rows):
        result = attach_specs_destacados(MagicMock(), [{"id": 1}])
    assert result[0]["specs_destacados"] == []


def test_destacados_dedup_por_label_gana_mayor_prioridad():
    rows = {1: [
        _row(1, "a", "Repetido", "string", "primero", prioridad=20, en_card=True),
        _row(1, "b", "Repetido", "string", "segundo", prioridad=10, en_card=True),
    ]}
    with _mock_rows(rows):
        result = attach_specs_destacados(MagicMock(), [{"id": 1}])
    destacados = result[0]["specs_destacados"]
    assert len(destacados) == 1
    assert destacados[0]["value"] == "segundo"  # prioridad 10 gana sobre 20


def test_destacados_equipo_sin_resultados():
    with _mock_rows({1: [], 2: []}):
        result = attach_specs_destacados(MagicMock(), [{"id": 1}, {"id": 2}])
    assert result[0]["specs_destacados"] == []
    assert result[1]["specs_destacados"] == []


def test_destacados_early_return_lista_vacia():
    result = attach_specs_destacados(MagicMock(), [])
    assert result == []


# ── attach_specs_estructuradas ───────────────────────────────────────────────


def test_estructuradas_incluye_flags_y_prioridad():
    rows = {1: [_row(1, "focal", "Focal", "number", "50", unidad="mm",
                      prioridad=10, en_card=True, en_filtros=False, destacado=True)]}
    with _mock_rows(rows):
        result = attach_specs_estructuradas(MagicMock(), [{"id": 1}])
    spec = result[0]["specs"]["focal"]
    assert spec["en_card"] is True
    assert spec["en_filtros"] is False
    assert spec["destacado"] is True
    assert spec["prioridad"] == 10
    assert spec["label"] == "Focal"
    assert spec["value_display"] == "50 mm"


def test_estructuradas_bool_false_se_omite_de_la_ficha():
    """A diferencia del preview pre-persist (que muestra 'No' explícito),
    la ficha pública omite bool=false por completo — no aporta al lector."""
    rows = {1: [_row(1, "iris", "Iris incluido", "bool", "false")]}
    with _mock_rows(rows):
        result = attach_specs_estructuradas(MagicMock(), [{"id": 1}])
    assert result[0]["specs"] == {}


def test_estructuradas_value_vacio_se_omite():
    rows = {1: [_row(1, "vacio", "Vacío", "string", "")]}
    with _mock_rows(rows):
        result = attach_specs_estructuradas(MagicMock(), [{"id": 1}])
    assert result[0]["specs"] == {}


def test_estructuradas_dedup_por_spec_key_gana_el_primero():
    """get_equipo_specs_rows ya devuelve deduped/ordenado por prioridad —
    el caller solo se queda con la primera aparición de cada spec_key."""
    rows = {1: [
        _row(1, "focal", "Focal", "number", "primero", prioridad=10),
        _row(1, "focal", "Focal", "number", "segundo", prioridad=20),
    ]}
    with _mock_rows(rows):
        result = attach_specs_estructuradas(MagicMock(), [{"id": 1}])
    assert result[0]["specs"]["focal"]["value"] == "primero"


def test_estructuradas_early_return_lista_vacia():
    result = attach_specs_estructuradas(MagicMock(), [])
    assert result == []
