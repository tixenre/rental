"""Tests Fase 6c-ii: split shutter_type + purga del seeder.

Cubre:
1. _parse_shutter_mechanism: Mechanical / Electronic / Hybrid
2. _parse_shutter_scan: Global Shutter / Rolling Shutter
3. canonicalizar_specs routing: un raw puede poblar ambas specs independientemente
4. purge_stale_specs: borra lo que no está en el registry, respeta lo que sí está
5. dry_run: nunca borra
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

_TOOLS = Path(__file__).resolve().parent.parent.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from camaras_normalizar import (
    _parse_shutter_mechanism,
    _parse_shutter_scan,
    canonicalizar_specs,
)


# ── _parse_shutter_mechanism ────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("Mechanical",                    "Mechanical"),
    ("Electronic",                    "Electronic"),
    ("Mechanical/Electronic Shutter", "Hybrid"),
    ("Global Shutter",                None),   # readout, no mecanismo
    ("Rolling Shutter",               None),   # readout, no mecanismo
    ("Electronic/Rolling Shutter",    "Electronic"),
    ("",                              None),
    (None,                            None),
])
def test_parse_shutter_mechanism(raw, expected):
    assert _parse_shutter_mechanism(raw) == expected


# ── _parse_shutter_scan ─────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("Global Shutter",             "Global Shutter"),
    ("Rolling Shutter",            "Rolling Shutter"),
    ("Electronic/Rolling Shutter", "Rolling Shutter"),
    ("Mechanical",                 None),
    ("Electronic",                 None),
    ("Hybrid",                     None),
    ("",                           None),
    (None,                         None),
])
def test_parse_shutter_scan(raw, expected):
    assert _parse_shutter_scan(raw) == expected


# ── canonicalizar_specs routing ─────────────────────────────────────────────

def test_routing_mechanical_solo():
    out = canonicalizar_specs({}, {"shutter_type": "Mechanical"})
    assert out.get("shutter_type") == "Mechanical"
    assert "shutter_scan" not in out


def test_routing_global_shutter_solo():
    out = canonicalizar_specs({}, {"shutter_type": "Global Shutter"})
    assert out.get("shutter_scan") == "Global Shutter"
    assert "shutter_type" not in out


def test_routing_rolling_shutter_solo():
    out = canonicalizar_specs({}, {"shutter_type": "Rolling Shutter"})
    assert out.get("shutter_scan") == "Rolling Shutter"
    assert "shutter_type" not in out


def test_routing_combined_electronic_rolling():
    """'Electronic/Rolling Shutter' puebla ambas specs independientemente."""
    out = canonicalizar_specs({}, {"shutter_type": "Electronic/Rolling Shutter"})
    assert out.get("shutter_type") == "Electronic"
    assert out.get("shutter_scan") == "Rolling Shutter"


def test_routing_sensor_readout_raw():
    """Campo B&H 'Sensor Readout' capturado como sensor_readout_raw → shutter_scan."""
    out = canonicalizar_specs({}, {"sensor_readout_raw": "Global Shutter"})
    assert out.get("shutter_scan") == "Global Shutter"


def test_routing_specs_wins_over_extras():
    """Si shutter_type ya está en specs, extras no lo pisa."""
    out = canonicalizar_specs({"shutter_type": "Mechanical"}, {"shutter_type": "Electronic"})
    assert out["shutter_type"] == "Mechanical"


# ── purge_stale_specs ───────────────────────────────────────────────────────

class _FakeRow:
    """Simula row de psycopg que soporta acceso por nombre y por índice."""
    def __init__(self, d: dict):
        self._d = d

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._d.values())[key]
        return self._d[key]

    def __iter__(self):
        return iter(self._d.values())


def _make_conn(spec_rows, categoria_id=1):
    """Mock de psycopg connection para tests de purge.

    spec_rows: list[dict] con las filas que devuelve SELECT id,spec_key FROM spec_definitions.
    """
    conn = MagicMock()
    call_count = [0]

    def execute_side_effect(query, params=None):
        q = str(query).strip()
        mock_cur = MagicMock()
        call_count[0] += 1

        if "categorias" in q and "nombre" in q:
            mock_cur.fetchone.return_value = _FakeRow({"id": categoria_id})
        elif "spec_definitions" in q and "SELECT id, spec_key" in q:
            mock_cur.fetchall.return_value = [_FakeRow(r) for r in spec_rows]
        else:
            mock_cur.fetchone.return_value = None
            mock_cur.fetchall.return_value = []
        return mock_cur

    conn.execute.side_effect = execute_side_effect
    return conn


def test_purge_removes_stale_specs():
    from services.specs import purge_stale_specs

    # DB tiene 'shutter_type' (en registry) + 'old_dead_spec' (no en registry)
    spec_rows = [
        {"id": 10, "spec_key": "shutter_type"},
        {"id": 99, "spec_key": "old_dead_spec"},
    ]
    conn = _make_conn(spec_rows)

    result = purge_stale_specs(conn, "Cámaras", dry_run=False)

    assert "old_dead_spec" in result["to_delete"]
    assert "shutter_type" not in result["to_delete"]
    assert result["deleted"] == 1
    assert result["dry_run"] is False


def test_purge_keeps_registry_specs():
    from services.specs import purge_stale_specs

    spec_rows = [{"id": 10, "spec_key": "shutter_type"}]
    conn = _make_conn(spec_rows)

    result = purge_stale_specs(conn, "Cámaras", dry_run=False)

    assert result["to_delete"] == []
    assert result["kept"] == 1
    assert result["deleted"] == 0


def test_purge_dry_run_no_delete():
    from services.specs import purge_stale_specs

    spec_rows = [
        {"id": 10, "spec_key": "shutter_type"},
        {"id": 99, "spec_key": "old_dead_spec"},
    ]
    conn = _make_conn(spec_rows)

    result = purge_stale_specs(conn, "Cámaras", dry_run=True)

    assert "old_dead_spec" in result["to_delete"]
    assert result["deleted"] == 0
    assert result["dry_run"] is True
    # Verifica que NO se llamó DELETE
    calls = [str(c) for c in conn.execute.call_args_list]
    assert not any("DELETE" in c for c in calls)


def test_purge_empty_db():
    from services.specs import purge_stale_specs

    conn = _make_conn(spec_rows=[])
    result = purge_stale_specs(conn, "Cámaras", dry_run=False)

    assert result["to_delete"] == []
    assert result["deleted"] == 0
