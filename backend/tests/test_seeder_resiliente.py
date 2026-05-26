"""Tests Fase 6f — seeder resiliente por categoría.

Cubre:
1. seed_all_categorias aísla fallos por categoría via SAVEPOINT: una categoría
   rota no tumba las demás.
2. purge_stale_specs efectivamente elimina specs cuya key ya no está en el
   registry (complementa test_shutter_split_purge — acá enfocado en la purga
   como parte del flujo de seeding completo).
"""

import sys
from unittest.mock import MagicMock, call, patch

import pytest

pytestmark = pytest.mark.unit


# ── helpers ──────────────────────────────────────────────────────────────────


class _FakeRow:
    def __init__(self, d: dict):
        self._d = d

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._d.values())[key]
        return self._d[key]


# ── FIX 1: aislamiento por SAVEPOINT ─────────────────────────────────────────


def _make_conn_tracking():
    """Conn mock que registra todas las llamadas a execute."""
    conn = MagicMock()
    executed = []

    def execute_side(query, params=None):
        executed.append(str(query).strip())
        cur = MagicMock()
        cur.fetchone.return_value = None
        cur.fetchall.return_value = []
        return cur

    conn.execute.side_effect = execute_side
    conn._executed = executed
    return conn


def test_seed_all_categorias_usa_savepoints():
    """seed_all_categorias emite SAVEPOINT y RELEASE por categoría."""
    conn = _make_conn_tracking()

    # Parchamos seed_categoria_from_registry para que no toque la DB real.
    with patch("seeds.registry_seeder.seed_categoria_from_registry") as mock_seed:
        mock_seed.return_value = {
            "raiz_id": 1, "subcat_ids": {}, "spec_def_ids": {},
            "stats": {"specs_creadas": 0, "specs_purgadas": 0},
            "purge": {},
        }
        from seeds.registry_seeder import seed_all_categorias, REGISTRY
        result = seed_all_categorias(conn, dry_run=False)

    savepoints = [q for q in conn._executed if "SAVEPOINT" in q.upper()]
    # Debe haber al menos un SAVEPOINT y un RELEASE por categoría.
    assert any("SAVEPOINT cat_" in q for q in savepoints), "Falta SAVEPOINT"
    assert any("RELEASE SAVEPOINT cat_" in q for q in savepoints), "Falta RELEASE"
    # Todas las categorías fueron procesadas.
    assert set(result["categorias"].keys()) == set(REGISTRY.categorias.keys())


def test_seed_all_categorias_continua_si_una_falla():
    """Si una categoría lanza excepción, las demás igualmente se procesan."""
    from seeds.registry_seeder import seed_all_categorias, REGISTRY

    nombres = list(REGISTRY.categorias.keys())
    assert len(nombres) >= 2, "Necesitamos al menos 2 categorías para este test"
    nombre_rota = nombres[0]
    nombre_ok = nombres[1]

    call_count = {"n": 0}

    def fake_seed(conn, nombre, dry_run=False):
        call_count["n"] += 1
        if nombre == nombre_rota:
            raise RuntimeError("categoría rota simulada")
        return {
            "raiz_id": 1, "subcat_ids": {}, "spec_def_ids": {},
            "stats": {"specs_creadas": 3, "specs_purgadas": 0},
            "purge": {},
        }

    conn = _make_conn_tracking()
    with patch("seeds.registry_seeder.seed_categoria_from_registry", side_effect=fake_seed):
        result = seed_all_categorias(conn, dry_run=False)

    # La categoría rota no aparece en el resultado pero las demás sí.
    assert nombre_rota not in result["categorias"]
    assert nombre_ok in result["categorias"]
    # Se llamó ROLLBACK TO SAVEPOINT para la categoría rota.
    rollbacks = [q for q in conn._executed if "ROLLBACK TO SAVEPOINT" in q.upper()]
    assert rollbacks, "Falta ROLLBACK TO SAVEPOINT tras el fallo"
    # Las demás tuvieron su RELEASE.
    releases = [q for q in conn._executed if "RELEASE SAVEPOINT" in q.upper()]
    assert releases, "Falta RELEASE SAVEPOINT para categorías exitosas"


def test_seed_all_categorias_dry_run_no_savepoints():
    """En dry_run no se emiten SAVEPOINTs (no hay transacción real)."""
    conn = _make_conn_tracking()
    with patch("seeds.registry_seeder.seed_categoria_from_registry") as mock_seed:
        mock_seed.return_value = {
            "raiz_id": None, "subcat_ids": {}, "spec_def_ids": {},
            "stats": {"specs_creadas": 0, "specs_purgadas": 0},
            "purge": {},
        }
        from seeds.registry_seeder import seed_all_categorias
        seed_all_categorias(conn, dry_run=True)

    savepoints = [q for q in conn._executed if "SAVEPOINT" in q.upper()]
    assert not savepoints, f"dry_run no debe emitir SAVEPOINTs, pero se emitieron: {savepoints}"


# ── FIX 1: purga efectiva de specs stale ─────────────────────────────────────


def _make_purge_conn(spec_rows, categoria_id=1):
    conn = MagicMock()

    def execute_side(query, params=None):
        q = str(query).strip()
        cur = MagicMock()
        if "categorias" in q and "nombre" in q:
            cur.fetchone.return_value = _FakeRow({"id": categoria_id})
        elif "spec_definitions" in q and "SELECT id, spec_key" in q:
            cur.fetchall.return_value = [_FakeRow(r) for r in spec_rows]
        else:
            cur.fetchone.return_value = None
            cur.fetchall.return_value = []
        return cur

    conn.execute.side_effect = execute_side
    return conn


def test_purge_elimina_spec_stale_en_modificadores():
    """purge_stale_specs borra una spec que existía en DB pero ya no en el registry."""
    from seeds.registry_seeder import purge_stale_specs

    spec_rows = [
        {"id": 10, "spec_key": "modificador_subtipo"},  # en registry
        {"id": 99, "spec_key": "spec_obsoleta_inexistente"},  # stale
    ]
    conn = _make_purge_conn(spec_rows)

    result = purge_stale_specs(conn, "Modificadores", dry_run=False)

    assert "spec_obsoleta_inexistente" in result["to_delete"]
    assert "modificador_subtipo" not in result["to_delete"]
    assert result["deleted"] == 1
    assert result["dry_run"] is False
    # Verificar que se ejecutó DELETE
    delete_calls = [
        str(c) for c in conn.execute.call_args_list
        if "DELETE" in str(c).upper()
    ]
    assert delete_calls, "Se esperaba un DELETE para la spec stale"
