"""Tests de services/specs/queries/equipo_specs.py::get_equipo_specs_rows.

Antes esta SQL vivía duplicada e inline en `database/equipos.py`
(`attach_specs_estructuradas` + `attach_specs_destacados`, cada una con su
propio JOIN contra equipo_specs+spec_definitions+categoria_spec_templates).
Estos asserts de forma del SQL vivían en `tests/test_attach_specs.py` — se
mudan acá junto con el query; `test_attach_specs.py` ahora testea la
política de display de cada caller sobre los rows ya resueltos.
"""

import sys
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

for _mod in ("psycopg2", "psycopg2.extras", "psycopg2.pool"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from services.specs.queries.equipo_specs import get_equipo_specs_rows


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Conn:
    """Fake conn con `.execute()` (estilo PGConnection), captura el SQL."""

    def __init__(self, rows):
        self._rows = rows
        self.last_sql = ""
        self.last_params = None

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = params
        return _Result(self._rows)


def test_early_return_lista_vacia():
    conn = _Conn([])
    assert get_equipo_specs_rows(conn, []) == {}
    assert conn.last_sql == ""  # ni siquiera ejecuta el IN () inválido


def test_sql_usa_sd_favorito_no_t_destacado():
    conn = _Conn([])
    get_equipo_specs_rows(conn, [1])
    assert "sd.favorito" in conn.last_sql
    assert "t.destacado" not in conn.last_sql


def test_sql_usa_sd_prioridad_no_t_prioridad():
    conn = _Conn([])
    get_equipo_specs_rows(conn, [1])
    assert "sd.prioridad" in conn.last_sql
    assert "t.prioridad" not in conn.last_sql


def test_sql_dedup_distinct_on_equipo_spec_def():
    conn = _Conn([])
    get_equipo_specs_rows(conn, [1])
    assert "DISTINCT ON (es.equipo_id, sd.id)" in conn.last_sql


def test_agrupa_rows_por_equipo_id():
    rows = [
        {"equipo_id": 1, "spec_def_id": 10, "spec_key": "focal", "label": "Focal",
         "tipo": "number", "unidad": "mm", "value": "50", "prioridad": 10,
         "en_card": True, "en_filtros": False, "destacado": True},
        {"equipo_id": 2, "spec_def_id": 11, "spec_key": "peso_g", "label": "Peso",
         "tipo": "number", "unidad": "g", "value": "300", "prioridad": 20,
         "en_card": False, "en_filtros": False, "destacado": False},
    ]
    conn = _Conn(rows)
    out = get_equipo_specs_rows(conn, [1, 2, 3])
    assert [r["spec_key"] for r in out[1]] == ["focal"]
    assert [r["spec_key"] for r in out[2]] == ["peso_g"]
    assert out[3] == []  # equipo sin specs: lista vacía, no KeyError


def test_placeholders_matchean_cantidad_de_ids():
    conn = _Conn([])
    get_equipo_specs_rows(conn, [1, 2, 3])
    assert conn.last_params == (1, 2, 3)
    assert conn.last_sql.count("%s") == 3
