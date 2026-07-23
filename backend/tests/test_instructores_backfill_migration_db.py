"""Regresión del hallazgo del supervisor en la revisión de F3 (PR #1281,
Escuela v2 #1278): el backfill de la migración `esc3n4t5r6u7` deduplicaba
instructores con `SELECT DISTINCT` sobre las 4 columnas (nombre/bio/foto),
no por nombre — dos talleres con el MISMO instructor pero bio/foto que
difieren aunque sea un carácter (ej. un typo corregido en uno y no en el
otro) generaban 2 filas en `instructores` en vez de 1.

Simula el camino real: `init_db()` (esquema al día, SIN backfillear — eso
es responsabilidad de la migración, no de init_db) + 2 `talleres` "legacy"
con el mismo `instructor_nombre` pero bio distinta + `alembic upgrade head`
(aplica el backfill). Verifica que dedupea por NOMBRE (1 sola fila) y que
AMBOS talleres quedan linkeados a esa misma fila.

OPT-IN y SEGURO POR DEFECTO (mismo gating que
test_backfill_descuento_cliente_pct_migration_db.py): se saltea salvo
ALEMBIC_DB_TEST=1 + DATABASE_URL a una base de prueba.
"""
import os
from pathlib import Path
from urllib.parse import urlparse

import pytest

_OPT_IN = os.getenv("ALEMBIC_DB_TEST") == "1"
_DB_URL = os.getenv("DATABASE_URL", "")
_DB_NAME = urlparse(_DB_URL).path.lstrip("/") if _DB_URL else ""


def _looks_like_test_db() -> bool:
    return bool(_DB_NAME) and "test" in _DB_NAME.lower()


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _OPT_IN,
        reason="opt-in: setear ALEMBIC_DB_TEST=1 + DATABASE_URL a una base de prueba",
    ),
    pytest.mark.skipif(
        _OPT_IN and not _looks_like_test_db(),
        reason=f"DATABASE_URL ({_DB_NAME!r}) no parece base de test — abortado por seguridad",
    ),
]

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    return cfg


def _reset_schema():
    from database import get_db

    conn = get_db()
    try:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def clean_db():
    _reset_schema()
    yield
    _reset_schema()


TALLER_A = 9_840_001
TALLER_B = 9_840_002
NOMBRE_COMPARTIDO = "Test Backfill Dedup"


def test_backfill_instructores_dedupea_por_nombre_no_por_bio(clean_db):
    from alembic import command
    from database import init_db, get_db
    import migration_state

    init_db()

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO talleres (id, slug, slug_base, nombre, instructor_nombre, "
            "instructor_bio, fecha_inicio, fecha_fin) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (TALLER_A, "test-backfill-a", "test-backfill-a", "Taller A", NOMBRE_COMPARTIDO,
             "Bio con un typo", "2099-01-01", "2099-01-02"),
        )
        conn.execute(
            "INSERT INTO talleres (id, slug, slug_base, nombre, instructor_nombre, "
            "instructor_bio, fecha_inicio, fecha_fin) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (TALLER_B, "test-backfill-b", "test-backfill-b", "Taller B", NOMBRE_COMPARTIDO,
             "Bio sin el typo (corregida en este taller nada más)", "2099-02-01", "2099-02-02"),
        )
        conn.commit()
    finally:
        conn.close()

    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    head = migration_state._head_revision(cfg)
    current = migration_state._current_revision()
    assert current == head, f"La cadena quedó en {current!r}, head es {head!r}"

    conn = get_db()
    try:
        instructores = conn.execute(
            "SELECT id FROM instructores WHERE nombre = %s", (NOMBRE_COMPARTIDO,)
        ).fetchall()
        assert len(instructores) == 1, (
            f"esperaba 1 solo instructor '{NOMBRE_COMPARTIDO}', encontré {len(instructores)} "
            "— el backfill dedupeó por (nombre, bio, foto) en vez de por nombre"
        )
        instructor_id = instructores[0]["id"]

        links = conn.execute(
            "SELECT taller_id FROM taller_instructores WHERE instructor_id = %s "
            "ORDER BY taller_id",
            (instructor_id,),
        ).fetchall()
        assert [r["taller_id"] for r in links] == [TALLER_A, TALLER_B], (
            "ambos talleres deben quedar linkeados a la MISMA fila de instructor"
        )
    finally:
        conn.close()
