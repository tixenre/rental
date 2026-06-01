"""Tests Fase 6f keystone — columna aliases en init_db y cadena de Alembic.

Cubre:
1. database.py contiene el ALTER TABLE que agrega aliases a spec_definitions
   (garantía de que la columna existe aunque Alembic no haya llegado a
   b3d5e7f9a1c2).
2. La migración e8f4d9c2b1a3 (backfill_legacy) es no-op en DB limpia: si
   las columnas legacy no existen, retorna sin tocar equipo_fichas.
3. La cadena de Alembic tiene exactamente una head y ningún hueco (sin
   branches divergentes): Verifica que b3d5e7f9a1c2 es alcanzable.
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

BACKEND_ROOT = Path(__file__).resolve().parent.parent
VERSIONS_DIR = BACKEND_ROOT / "migrations" / "versions"


# ── FIX 1: aliases en init_db ─────────────────────────────────────────────────


def test_database_py_contiene_alter_aliases():
    """database.py debe tener el ALTER TABLE que agrega la columna aliases."""
    db_src = (BACKEND_ROOT / "database.py").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS aliases" in db_src, (
        "database.py no tiene el ALTER TABLE para aliases en spec_definitions. "
        "El seeder falla si Alembic no llega a b3d5e7f9a1c2."
    )
    # Verificar también que tiene el default JSON array correcto.
    assert "'[]'::jsonb" in db_src or "DEFAULT '[]'" in db_src, (
        "El ALTER TABLE de aliases debería incluir DEFAULT '[]'::jsonb"
    )


# ── FIX 2: backfill idempotente en DB limpia ──────────────────────────────────


def _load_migration(revision_id: str):
    """Importa una migración por su revision_id."""
    for path in VERSIONS_DIR.glob("*.py"):
        if path.stem.startswith(revision_id):
            spec = importlib.util.spec_from_file_location(f"mig_{path.stem}", path)
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise FileNotFoundError(f"No migration found for revision {revision_id}")


def test_backfill_noop_cuando_columnas_legacy_ausentes(monkeypatch):
    """e8f4d9c2b1a3: si equipo_fichas no tiene 'montura', upgrade() es no-op."""
    mod = _load_migration("e8f4d9c2b1a3")

    # Mock de op.get_bind() que devuelve 0 para la existencia de columna.
    mock_conn = MagicMock()
    mock_conn.execute.return_value.scalar.return_value = 0

    mock_op = MagicMock()
    mock_op.get_bind.return_value = mock_conn
    monkeypatch.setattr(mod, "op", mock_op)

    # Debe retornar sin lanzar excepción y sin hacer INSERTs.
    mod.upgrade()

    # Verificar que ejecutó solo el check de information_schema, no más.
    assert mock_conn.execute.call_count == 1, (
        "Con columnas ausentes, upgrade() debe ejecutar solo el check de existencia"
    )
    # El argumento es un TextClause — comparar su texto compilado.
    call_arg = mock_conn.execute.call_args[0][0]
    call_sql = str(call_arg) if hasattr(call_arg, "text") else str(call_arg)
    assert "information_schema" in call_sql or "montura" in call_sql, (
        f"La única ejecución debe ser el check de columna, got: {call_sql!r}"
    )


def test_backfill_ejecuta_cuando_columna_existe(monkeypatch):
    """e8f4d9c2b1a3: si 'montura' existe, upgrade() avanza (puede fallar por mock
    incompleto, pero no debe hacer early-return)."""
    mod = _load_migration("e8f4d9c2b1a3")

    call_log = []

    def execute_side(query, *args, **kwargs):
        call_log.append(str(query))
        cur = MagicMock()
        cur.scalar.return_value = 1   # columna existe
        cur.fetchall.return_value = []  # sin filas → loop vacío
        cur.fetchone.return_value = None
        return cur

    mock_conn = MagicMock()
    mock_conn.execute.side_effect = execute_side

    mock_op = MagicMock()
    mock_op.get_bind.return_value = mock_conn
    monkeypatch.setattr(mod, "op", mock_op)

    mod.upgrade()

    # Debe haber ejecutado más de 1 query (el check + los 6 SELECT de columnas legacy).
    assert mock_conn.execute.call_count > 1, (
        "Con columnas presentes, upgrade() debe ejecutar el backfill completo"
    )


# ── Cadena de Alembic sin huecos ──────────────────────────────────────────────


def _parse_all_revisions() -> dict[str, list[str]]:
    """Devuelve {revision_id: [parent_ids]} para todas las migraciones.

    Parsea los archivos como texto con regex en vez de importarlos para
    evitar dependencias en sqlalchemy/alembic/psycopg2 en el entorno de test.

    Los revision IDs de Alembic no son estrictamente hex — pueden contener
    cualquier caracter alfanumérico. down_revision puede ser None, una cadena
    simple o una tupla de IDs (en migraciones de merge).
    """
    import re
    result = {}
    rev_re = re.compile(r'^revision\s*(?::\s*\w+\s*)?\=\s*["\']([a-z0-9]+)["\']', re.M)
    down_line_re = re.compile(r'^down_revision\s*(?::[^=]+)?\=\s*(.+)', re.M)
    id_re = re.compile(r'["\']([a-z0-9]+)["\']')

    for path in VERSIONS_DIR.glob("*.py"):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        rev_m = rev_re.search(text)
        if not rev_m:
            continue
        rev = rev_m.group(1)
        down_m = down_line_re.search(text)
        parents = id_re.findall(down_m.group(1)) if down_m else []
        result[rev] = parents
    return result


def test_cadena_alembic_sin_head_divergentes():
    """No debe haber branches divergentes: exactamente una head."""
    revisions = _parse_all_revisions()
    all_revs = set(revisions.keys())
    parents = {p for ps in revisions.values() for p in ps}
    # Las heads son las revisiones que no son parent de nadie.
    heads = all_revs - parents
    assert len(heads) == 1, (
        f"Se esperaba 1 head, se encontraron {len(heads)}: {heads}. "
        "Hay branches divergentes en las migraciones."
    )


def test_b3d5e7f9a1c2_alcanzable_desde_baseline():
    """b3d5e7f9a1c2 (agrega aliases) debe ser alcanzable desde el baseline."""
    TARGET = "b3d5e7f9a1c2"
    revisions = _parse_all_revisions()

    assert TARGET in revisions, f"Migración {TARGET} no encontrada en versions/"

    # Trazar cadena desde TARGET hasta el baseline (down_revision=None).
    visited = set()
    current = TARGET
    while current is not None:
        if current in visited:
            pytest.fail(f"Ciclo detectado en la cadena de migraciones en {current}")
        visited.add(current)
        parents = revisions.get(current, [])
        current = parents[0] if parents else None

    # Si llegamos hasta None sin errores, la cadena es válida desde TARGET.
    assert TARGET in visited


def test_cadena_no_tiene_huecos():
    """Cada down_revision referencia una revision que existe."""
    revisions = _parse_all_revisions()
    for rev, parents in revisions.items():
        for parent in parents:
            assert parent in revisions, (
                f"Migración {rev} referencia parent {parent} que no existe en versions/"
            )
