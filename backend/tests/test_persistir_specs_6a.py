"""Tests Sub-fase 6a — persistir_specs + match difuso de enums.

Cubre:
- _coerce_enum: match por substring ("Wi-Fi 6 (802.11ax)" → "Wi-Fi")
- _coerce_multi_enum: split B&H slash/CSV → canónico sin 400; descarte silencioso
- persistir_specs: path del form PUT /specs con DB in-memory
  · multi_enum crudo B&H → guarda canónico
  · number con unidad → guarda número
  · enum case-insensitive → guarda canónico
  · valor sin match → descartado, reportado, sin row en DB

`spec_value_aliases` está en el schema aunque estos tests no siembren alias
(queda vacía): persistir_specs consulta esa tabla vía el embudo (#1163 F3,
mapear_valor) para tipo=enum antes de coerce_and_serialize.
"""

import json
import sqlite3

import pytest

pytestmark = pytest.mark.unit

from services.specs.commands.persist import persistir_specs


class _SQLiteAdapter:
    """Wraps sqlite3.Connection translating %s placeholders to ? so unit tests
    keep using in-memory SQLite after the service migrated to %s nativo."""
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self.row_factory = conn.row_factory

    def execute(self, sql: str, params=()):
        return self._conn.execute(sql.replace("%s", "?"), params)

    def commit(self):
        return self._conn.commit()


def _setup_db() -> _SQLiteAdapter:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE equipos (id INTEGER PRIMARY KEY, slug TEXT);
        INSERT INTO equipos VALUES (1, 'test-equipo');
        CREATE TABLE spec_definitions (
            id INTEGER PRIMARY KEY,
            label TEXT,
            tipo TEXT,
            unidad TEXT,
            enum_options TEXT,
            tabla_columnas TEXT
        );
        CREATE TABLE equipo_specs (
            equipo_id INTEGER,
            spec_def_id INTEGER,
            value TEXT,
            PRIMARY KEY (equipo_id, spec_def_id)
        );
        CREATE TABLE spec_value_aliases (
            spec_def_id INTEGER,
            alias TEXT,
            valor_canonico TEXT,
            PRIMARY KEY (spec_def_id, alias)
        );
    """)
    return _SQLiteAdapter(conn)


# ── _coerce_enum: match difuso por substring ─────────────────────────────────


def test_coerce_enum_fuzzy_opt_in_input():
    from services.specs.commands.coerce import _coerce_enum
    opts = ["Wi-Fi", "Bluetooth", "NFC"]
    assert _coerce_enum("Wi-Fi 6 (802.11ax)", opts) == "Wi-Fi"


def test_coerce_enum_fuzzy_case_insensitive():
    from services.specs.commands.coerce import _coerce_enum
    opts = ["Wi-Fi", "Bluetooth"]
    assert _coerce_enum("wi-fi 6 (802.11ax)", opts) == "Wi-Fi"



def test_coerce_enum_fuzzy_no_match_es_none():
    from services.specs.commands.coerce import _coerce_enum
    opts = ["Wi-Fi", "Bluetooth"]
    assert _coerce_enum("Zigbee", opts) is None


def test_coerce_enum_fuzzy_no_match_pl_mount():
    # Regresión: "PL-Mount" no matchea "E-Mount" ni "F-Mount" por substring
    from services.specs.commands.coerce import _coerce_enum
    opts = ["E-Mount", "F-Mount"]
    assert _coerce_enum("PL-Mount", opts) is None


def test_coerce_enum_fuzzy_lista_vacia_es_none():
    from services.specs.commands.coerce import _coerce_enum
    assert _coerce_enum("Wi-Fi 6", []) is None


# ── _coerce_multi_enum: fuzzy match por parte ────────────────────────────────


def test_coerce_multi_enum_bh_slash_raw():
    from services.specs.commands.coerce import _coerce_multi_enum
    opts = ["Wi-Fi", "Bluetooth", "NFC"]
    result = _coerce_multi_enum("Wi-Fi 6 (802.11ax) / Bluetooth", opts)
    assert json.loads(result) == ["Wi-Fi", "Bluetooth"]


def test_coerce_multi_enum_match_parcial_descarta_desconocidos():
    from services.specs.commands.coerce import _coerce_multi_enum
    opts = ["Wi-Fi", "Bluetooth"]
    result = _coerce_multi_enum("Wi-Fi 6 (802.11ax) / Zigbee desconocido", opts)
    assert json.loads(result) == ["Wi-Fi"]


def test_coerce_multi_enum_nada_mapea_devuelve_none():
    from services.specs.commands.coerce import _coerce_multi_enum
    opts = ["Wi-Fi", "Bluetooth"]
    assert _coerce_multi_enum("Zigbee / Z-Wave", opts) is None


def test_coerce_multi_enum_sin_opts_devuelve_raw():
    from services.specs.commands.coerce import _coerce_multi_enum
    result = _coerce_multi_enum("AC, DC, Battery", [])
    assert json.loads(result) == ["AC", "DC", "Battery"]


def test_coerce_multi_enum_dedup():
    from services.specs.commands.coerce import _coerce_multi_enum
    opts = ["Wi-Fi", "Bluetooth"]
    result = _coerce_multi_enum("Wi-Fi 6 / Wi-Fi 5", opts)
    assert json.loads(result) == ["Wi-Fi"]


# ── persistir_specs: path del form (PUT /specs) ──────────────────────────────


def test_persistir_specs_multi_enum_bh_sin_400():
    conn = _setup_db()
    conn.execute(
        "INSERT INTO spec_definitions (id, label, tipo, enum_options) "
        "VALUES (1, 'Conectividad', 'multi_enum', '[\"Wi-Fi\", \"Bluetooth\", \"NFC\"]')"
    )
    conn.commit()

    defs_by_id = {
        1: {
            "id": 1, "label": "Conectividad", "tipo": "multi_enum",
            "enum_options": '["Wi-Fi", "Bluetooth", "NFC"]', "unidad": None,
            "tabla_columnas": None,
        }
    }
    result = persistir_specs(conn, 1, {"1": "Wi-Fi 6 (802.11ax) / Bluetooth"}, defs_by_id)

    row = conn.execute(
        "SELECT value FROM equipo_specs WHERE equipo_id=1 AND spec_def_id=1"
    ).fetchone()
    assert row is not None
    assert json.loads(row["value"]) == ["Wi-Fi", "Bluetooth"]
    assert result["persisted"] == 1
    assert result["discarded"] == []


def test_persistir_specs_number_con_unidad():
    conn = _setup_db()
    conn.execute(
        "INSERT INTO spec_definitions (id, label, tipo, unidad) VALUES (2, 'Peso', 'number', 'g')"
    )
    conn.commit()

    defs_by_id = {
        2: {"id": 2, "label": "Peso", "tipo": "number", "enum_options": None,
            "unidad": "g", "tabla_columnas": None}
    }
    result = persistir_specs(conn, 1, {"2": "890 g"}, defs_by_id)

    row = conn.execute(
        "SELECT value FROM equipo_specs WHERE equipo_id=1 AND spec_def_id=2"
    ).fetchone()
    assert row is not None
    assert row["value"] == "890"
    assert result["persisted"] == 1


def test_persistir_specs_enum_case_insensitive():
    conn = _setup_db()
    conn.execute(
        "INSERT INTO spec_definitions (id, label, tipo, enum_options) "
        "VALUES (3, 'Montura', 'enum', '[\"E-Mount\", \"F-Mount\", \"RF\"]')"
    )
    conn.commit()

    defs_by_id = {
        3: {"id": 3, "label": "Montura", "tipo": "enum",
            "enum_options": '["E-Mount", "F-Mount", "RF"]', "unidad": None,
            "tabla_columnas": None}
    }
    result = persistir_specs(conn, 1, {"3": "e-mount"}, defs_by_id)

    row = conn.execute(
        "SELECT value FROM equipo_specs WHERE equipo_id=1 AND spec_def_id=3"
    ).fetchone()
    assert row is not None
    assert row["value"] == "E-Mount"
    assert result["persisted"] == 1


def test_persistir_specs_usa_embudo_de_alias_de_valor():
    """#1163 F3: 'FF' no matchea 'Full-frame' por substring (old _coerce_enum
    lo hubiera descartado) — pero SÍ vía spec_value_aliases (el embudo)."""
    conn = _setup_db()
    conn.execute(
        "INSERT INTO spec_definitions (id, label, tipo, enum_options) "
        "VALUES (5, 'Formato', 'enum', '[\"Full-frame\", \"Super 35\"]')"
    )
    conn.execute(
        "INSERT INTO spec_value_aliases (spec_def_id, alias, valor_canonico) "
        "VALUES (5, 'FF', 'Full-frame')"
    )
    conn.commit()

    defs_by_id = {
        5: {"id": 5, "label": "Formato", "tipo": "enum",
            "enum_options": '["Full-frame", "Super 35"]', "unidad": None,
            "tabla_columnas": None}
    }
    result = persistir_specs(conn, 1, {"5": "FF"}, defs_by_id)

    row = conn.execute(
        "SELECT value FROM equipo_specs WHERE equipo_id=1 AND spec_def_id=5"
    ).fetchone()
    assert row is not None
    assert row["value"] == "Full-frame"
    assert result["persisted"] == 1
    assert result["discarded"] == []


def test_persistir_specs_valor_sin_match_se_descarta():
    conn = _setup_db()
    conn.execute(
        "INSERT INTO spec_definitions (id, label, tipo, enum_options) "
        "VALUES (4, 'Modo', 'enum', '[\"Auto\", \"Manual\"]')"
    )
    conn.commit()

    defs_by_id = {
        4: {"id": 4, "label": "Modo", "tipo": "enum",
            "enum_options": '["Auto", "Manual"]', "unidad": None,
            "tabla_columnas": None}
    }
    result = persistir_specs(conn, 1, {"4": "TotallyUnknown"}, defs_by_id)

    row = conn.execute(
        "SELECT value FROM equipo_specs WHERE equipo_id=1 AND spec_def_id=4"
    ).fetchone()
    assert row is None
    assert result["persisted"] == 0
    assert len(result["discarded"]) == 1
    assert result["discarded"][0]["spec_def_id"] == 4
    assert result["discarded"][0]["label"] == "Modo"


def test_persistir_specs_reemplaza_specs_anteriores():
    conn = _setup_db()
    conn.execute(
        "INSERT INTO spec_definitions (id, label, tipo) VALUES (5, 'Notas', 'string')"
    )
    conn.execute(
        "INSERT INTO equipo_specs (equipo_id, spec_def_id, value) VALUES (1, 5, 'viejo')"
    )
    conn.commit()

    defs_by_id = {
        5: {"id": 5, "label": "Notas", "tipo": "string", "enum_options": None,
            "unidad": None, "tabla_columnas": None}
    }
    persistir_specs(conn, 1, {"5": "nuevo"}, defs_by_id)

    row = conn.execute(
        "SELECT value FROM equipo_specs WHERE equipo_id=1 AND spec_def_id=5"
    ).fetchone()
    assert row["value"] == "nuevo"
