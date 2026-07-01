"""Embudo de alias de valor contra Postgres REAL (#1163 Fase 2).

Cubre lo que test_specs_value_aliases_model.py no puede sin DB:
1. _sync_value_aliases escribe filas, es idempotente (ON CONFLICT), y no
   escribe nada en dry_run.
2. mapear_valor resuelve: value ya canónico (con distinto casing/acentos/
   guiones), alias conocido, y None cuando no matchea nada.

Todavía sin consumidor real (coerce/validation no llaman a mapear_valor
hasta la Fase 3) — este test verifica el mecanismo en aislamiento.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los otros *_db.py): se saltea
salvo RESERVAS_DB_TEST=1 + DATABASE_URL con 'test' en el nombre. Ids altos
(categoría ancla) + limpieza vía CASCADE.
"""
import os
from urllib.parse import urlparse

import pytest

from services.specs.commands.seed import _sync_value_aliases, _upsert_spec_definition
from services.specs.normalize.value_funnel import mapear_valor
from services.specs.registry.models import SpecDef

_OPT_IN = os.getenv("RESERVAS_DB_TEST") == "1"
_DB_URL = os.getenv("DATABASE_URL", "")
_DB_NAME = urlparse(_DB_URL).path.lstrip("/") if _DB_URL else ""


def _looks_like_test_db() -> bool:
    return bool(_DB_NAME) and "test" in _DB_NAME.lower()


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _OPT_IN,
        reason="opt-in: setear RESERVAS_DB_TEST=1 + DATABASE_URL a una base de prueba",
    ),
    pytest.mark.skipif(
        _OPT_IN and not _looks_like_test_db(),
        reason=f"DATABASE_URL ({_DB_NAME!r}) no parece base de test — abortado por seguridad",
    ),
]

# Categoría ancla de id fijo alto — spec_definitions/spec_value_aliases cuelgan
# de acá por FK CASCADE, así que borrar la categoría limpia todo.
C_ANCLA = 9_400_201


def _limpiar(conn):
    conn.execute("DELETE FROM categorias WHERE id = %s", (C_ANCLA,))


@pytest.fixture
def spec_def_id():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO categorias (id, nombre) VALUES (%s, %s)",
            (C_ANCLA, "ZZ-EmbudoTest-test"),
        )
        spec = SpecDef(
            key="formato", label="Formato", tipo="enum",
            enum_options=["Full-frame", "Super 35"],
            value_aliases={
                "Full-frame": ["FF", "full frame", "cuadro completo"],
                "Super 35": ["S35"],
            },
        )
        sid = _upsert_spec_definition(conn, spec, C_ANCLA, dry_run=False)
        _sync_value_aliases(conn, sid, spec, dry_run=False)
        conn.commit()
    finally:
        conn.close()
    yield sid
    conn = get_db()
    try:
        _limpiar(conn)
        conn.commit()
    finally:
        conn.close()


class TestSyncValueAliases:
    def test_escribe_las_filas_declaradas(self, spec_def_id):
        from database import get_db

        with get_db() as conn:
            rows = conn.execute(
                "SELECT alias, valor_canonico FROM spec_value_aliases "
                "WHERE spec_def_id = %s ORDER BY alias",
                (spec_def_id,),
            ).fetchall()
        aliases = {r["alias"]: r["valor_canonico"] for r in rows}
        assert aliases == {
            "FF": "Full-frame",
            "full frame": "Full-frame",
            "cuadro completo": "Full-frame",
            "S35": "Super 35",
        }

    def test_idempotente_no_duplica(self, spec_def_id):
        from database import get_db

        spec = SpecDef(
            key="formato", label="Formato", tipo="enum",
            enum_options=["Full-frame", "Super 35"],
            value_aliases={"Full-frame": ["FF", "full frame", "cuadro completo"], "Super 35": ["S35"]},
        )
        with get_db() as conn:
            _sync_value_aliases(conn, spec_def_id, spec, dry_run=False)
            conn.commit()
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM spec_value_aliases WHERE spec_def_id = %s",
                (spec_def_id,),
            ).fetchone()
        assert total["c"] == 4

    def test_dry_run_no_escribe(self, spec_def_id):
        from database import get_db

        spec = SpecDef(key="otro", label="Otro", tipo="enum", enum_options=["A"], value_aliases={"A": ["a1"]})
        with get_db() as conn:
            n = _sync_value_aliases(conn, spec_def_id, spec, dry_run=True)
            existe = conn.execute(
                "SELECT 1 FROM spec_value_aliases WHERE alias = 'a1'"
            ).fetchone()
        assert n == 0
        assert existe is None


class TestMapearValor:
    @pytest.mark.parametrize("raw,esperado", [
        ("Full-frame", "Full-frame"),
        ("full-frame", "Full-frame"),
        ("FULL FRAME", "Full-frame"),
        ("FF", "Full-frame"),
        ("ff", "Full-frame"),
        ("Full Frame", "Full-frame"),
        ("cuadro completo", "Full-frame"),
        ("S35", "Super 35"),
        ("APS-C", None),
        ("", None),
    ])
    def test_casos(self, spec_def_id, raw, esperado):
        from database import get_db

        with get_db() as conn:
            assert mapear_valor(conn, spec_def_id, raw) == esperado

    def test_spec_def_id_inexistente_no_explota(self, spec_def_id):
        from database import get_db

        with get_db() as conn:
            assert mapear_valor(conn, 999_999_999, "FF") is None
