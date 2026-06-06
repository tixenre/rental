"""Tests de Fase 6d — attach_specs_destacados y attach_specs_estructuradas.

Verifica que los flags y la prioridad se lean de spec_definitions (sd),
no de categoria_spec_templates (t). La fuente canónica es sd.favorito,
sd.en_filtros, sd.en_nombre y sd.prioridad.
"""

import sys
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

# psycopg2 no está instalado en el entorno de tests — lo mockeamos antes de
# importar database.py para no necesitar la BD.
for _mod in ("psycopg2", "psycopg2.extras", "psycopg2.pool"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from database import attach_specs_destacados, attach_specs_estructuradas


class _Cursor:
    """Cursor fake que captura el SQL ejecutado y devuelve rows configurables."""

    def __init__(self, rows):
        self._rows = rows
        self.last_sql = ""

    def execute(self, sql, params=None):
        self.last_sql = sql

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _Conn:
    def __init__(self, rows):
        self._cursor = _Cursor(rows)

    def cursor(self):
        return self._cursor


# ── attach_specs_destacados ──────────────────────────────────────────────────


def test_destacados_sql_usa_sd_favorito():
    """La query filtra por sd.favorito, no por t.destacado."""
    conn = _Conn([])
    attach_specs_destacados(conn, [{"id": 1}])
    sql = conn._cursor.last_sql
    assert "sd.favorito" in sql, "Debe filtrar por sd.favorito"
    assert "t.destacado" not in sql, "No debe leer t.destacado (tabla legacy)"


def test_destacados_sql_ordena_por_sd_prioridad():
    """El ORDER BY usa sd.prioridad, no t.prioridad."""
    conn = _Conn([])
    attach_specs_destacados(conn, [{"id": 1}])
    sql = conn._cursor.last_sql
    assert "sd.prioridad" in sql, "Debe ordenar por sd.prioridad"
    assert "t.prioridad" not in sql, "No debe ordenar por t.prioridad (tabla legacy)"


def test_destacados_retorna_specs_con_bool_value():
    """Las specs bool destacadas se emiten con value='' (solo label como badge)."""
    rows = [
        {
            "equipo_id": 1,
            "label": "Macro",
            "tipo": "bool",
            "unidad": None,
            "value": "sí",
            "prioridad": 10,
        }
    ]
    conn = _Conn(rows)
    equipos = [{"id": 1}]
    result = attach_specs_destacados(conn, equipos)
    destacados = result[0]["specs_destacados"]
    assert len(destacados) == 1
    assert destacados[0]["label"] == "Macro"
    assert destacados[0]["value"] == ""  # bool → badge sin valor


def test_destacados_dedup_por_label():
    """Si el mismo label aparece dos veces, solo se incluye la primera vez."""
    rows = [
        {"equipo_id": 1, "label": "Macro", "tipo": "bool", "unidad": None, "value": "sí", "prioridad": 10},
        {"equipo_id": 1, "label": "Macro", "tipo": "bool", "unidad": None, "value": "sí", "prioridad": 20},
    ]
    conn = _Conn(rows)
    result = attach_specs_destacados(conn, [{"id": 1}])
    assert len(result[0]["specs_destacados"]) == 1


def test_destacados_equipo_sin_resultados():
    """Equipo sin specs destacadas recibe lista vacía."""
    conn = _Conn([])
    equipos = [{"id": 1}, {"id": 2}]
    result = attach_specs_destacados(conn, equipos)
    assert result[0]["specs_destacados"] == []
    assert result[1]["specs_destacados"] == []


def test_destacados_early_return_lista_vacia():
    conn = _Conn([])
    result = attach_specs_destacados(conn, [])
    assert result == []


# ── attach_specs_estructuradas ───────────────────────────────────────────────


def test_estructuradas_sql_usa_sd_flags():
    """La query lee en_card/en_filtros/destacado desde sd, no desde t."""
    conn = _Conn([])
    attach_specs_estructuradas(conn, [{"id": 1}])
    sql = conn._cursor.last_sql
    # Flags vienen de sd
    assert "sd.favorito" in sql, "en_card y destacado deben derivarse de sd.favorito"
    assert "sd.en_filtros" in sql, "en_filtros debe leerse de sd.en_filtros"
    assert "sd.prioridad" in sql, "prioridad debe leerse de sd.prioridad"
    # No debe leer flags de la tabla de templates
    assert "t.visible_en_card" not in sql
    assert "t.visible_en_filtros" not in sql
    assert "t.destacado" not in sql
    assert "t.prioridad" not in sql


def test_estructuradas_flags_mapeados_correctamente():
    """en_card y destacado se derivan de sd.favorito; en_filtros de sd.en_filtros."""
    rows = [
        {
            "equipo_id": 1,
            "spec_key": "focal",
            "label": "Focal",
            "tipo": "number",
            "unidad": "mm",
            "value": "50",
            "prioridad": 10,
            "en_card": True,      # sd.favorito → en_card
            "en_filtros": False,  # sd.en_filtros → en_filtros
            "destacado": True,    # sd.favorito → destacado
        }
    ]
    conn = _Conn(rows)
    result = attach_specs_estructuradas(conn, [{"id": 1}])
    spec = result[0]["specs"]["focal"]
    assert spec["en_card"] is True
    assert spec["en_filtros"] is False
    assert spec["destacado"] is True
    assert spec["prioridad"] == 10
    assert spec["label"] == "Focal"


def test_estructuradas_early_return_lista_vacia():
    conn = _Conn([])
    result = attach_specs_estructuradas(conn, [])
    assert result == []
