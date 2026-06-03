"""Corre las migraciones Alembic contra un Postgres REAL hasta el head.

El smoke test (`test_alembic.py`) verifica que la config carga y que las
migraciones son listables, pero NUNCA aplica una migración. Este test cierra ese
hueco: ejecuta la cadena completa contra una BD descartable y exige llegar al
head. Caza roturas **estructurales** antes de mergear — no-idempotencia,
multiple-heads, un `CREATE TABLE` sin guard, un `down_revision` colgado, etc.
(Las fallas *data-dependientes* —ej. la migración de slugs que aborta si hay
duplicados— no se reproducen acá porque la BD de test no tiene esos datos; esas
se cubren con la visibilidad de `/health/migrations` + el runbook.)

Reproduce el camino real del arranque (`backend/main.py::init_db_bg`):
**`init_db()` + `alembic upgrade head`**. `init_db()` crea el esquema idempotente
y las migraciones corren encima — las de esquema deben ser no-op (un `CREATE`
sin guard sobre una tabla ya creada por init_db explotaría acá) y las de datos
operan sobre las tablas que init_db dejó. Es el ÚNICO bootstrap soportado: la
cadena de migraciones NO se basta sola desde una BD vacía (p. ej. la migración
que normaliza `equipos.dueno` hace `UPDATE equipos`, que asume la tabla creada
por init_db).

OPT-IN y SEGURO POR DEFECTO: se saltea salvo que apuntes `DATABASE_URL` a una
base de PRUEBA descartable y prendas el opt-in. Nunca corre en el CI normal ni
toca prod. En CI lo dispara un job dedicado con un service Postgres efímero.

    createdb rambla_rental_test
    DATABASE_URL=postgresql://postgres:postgres@localhost/rambla_rental_test \
      ALEMBIC_DB_TEST=1 \
      python -m pytest tests/test_alembic_upgrade_db.py -v -m integration

Guard-rails (igual que test_reservas_concurrency_db.py):
  - Exige el opt-in explícito `ALEMBIC_DB_TEST=1`.
  - Se niega a correr si la `DATABASE_URL` no parece de test (nombre con 'test').
  - El fixture dropea y recrea el schema `public` — destructivo, por eso el
    guard de nombre es la red de seguridad.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

import pytest

# ── Gating: skip salvo opt-in explícito + DB de test ─────────────────────────

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
    """Misma config que arma el arranque real (backend/main.py)."""
    from alembic.config import Config

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    return cfg


def _reset_schema():
    """Deja el schema `public` vacío. Destructivo — el guard de nombre de DB es
    la red de seguridad (este código no corre salvo DB con 'test' en el nombre)."""
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
    """Schema vacío antes del test y limpio después (no dejar tablas colgadas)."""
    _reset_schema()
    yield
    _reset_schema()


def test_initdb_mas_upgrade_llega_al_head(clean_db):
    """Camino real de prod: init_db() (esquema idempotente) + upgrade head.
    Las migraciones de esquema deben ser no-op sobre lo que init_db ya creó y
    la cadena debe llegar igual al head."""
    from alembic import command
    from database import init_db
    import migration_state

    init_db()  # CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS

    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    head = migration_state._head_revision(cfg)
    current = migration_state._current_revision()
    assert current == head, (
        f"Tras init_db()+upgrade, la BD quedó en {current!r} pero el head es "
        f"{head!r} — alguna migración no es idempotente sobre init_db o la "
        f"cadena no llega al head."
    )


def test_upgrade_con_datos_legacy_llega_al_head(clean_db):
    """Regresión #690: el camino de prod NO es solo init_db()+upgrade en vacío.

    Cubre DOS bugs reales que solo se disparaban en prod (DB de larga vida con
    datos + tablas viejas), no en init_db en vacío:

    1. `e8f4d9c2b1a3` backfillea `equipo_specs` con `INSERT ... RETURNING id`,
       pero `equipo_specs` tiene PK compuesta y NO columna `id`. Solo pasaba en
       DBs SIN datos legacy (el INSERT nunca se ejecutaba); con datos abortaba la
       cadena (transacción única). Las columnas legacy ya no existen en el
       esquema canónico (las dropea `a1b3c5e7f9d2`), así que las recreamos.
    2. `l1m2n3o4p5q6` hace `INSERT INTO equipo_fotos (... url ...)`, pero en prod
       `equipo_fotos` preexistía SIN `url` (init_db viejo + CREATE IF NOT EXISTS);
       la columna recién se agrega en `n1o2p3q4r5s6` (head), DESPUÉS del backfill.
       Lo simulamos dropeando `url` y sembrando un equipo con `foto_url`.

    Se siembra un equipo mapeable + se exige que `upgrade head` llegue al head.
    """
    from alembic import command
    from database import init_db, get_db
    import migration_state

    init_db()

    conn = get_db()
    try:
        # Bug 1: columnas legacy (pre-drop) + equipo con `montura` mapeable a un
        # spec_def `lens_mount` en su categoría raíz.
        for col in ("montura", "formato", "resolucion", "peso", "dimensiones", "alimentacion"):
            conn.execute(f"ALTER TABLE equipo_fichas ADD COLUMN IF NOT EXISTS {col} TEXT")
        # Bug 2: equipo_fotos como en prod, una versión vieja a la que le faltan
        # `url` y `media_id` (los logs de prod muestran que k1l2m3n4o5p6 pasa —
        # su índice usa `orden`, que existe — y l1m2 falla primero por `url` y
        # luego por `media_id`). Fuerza a l1m2 a agregar esas columnas faltantes.
        conn.execute("DROP TABLE IF EXISTS equipo_fotos CASCADE")
        conn.execute(
            "CREATE TABLE equipo_fotos ("
            " id SERIAL PRIMARY KEY,"
            " equipo_id INTEGER NOT NULL REFERENCES equipos(id) ON DELETE CASCADE,"
            " orden INTEGER NOT NULL DEFAULT 0,"
            " es_principal BOOLEAN NOT NULL DEFAULT FALSE)"
        )
        # Equipo con foto_url para que el backfill de equipo_fotos (l1m2) inserte.
        conn.execute("INSERT INTO equipos (id, nombre, foto_url) VALUES (9001, 'repro #690', 'https://x/f.jpg') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO categorias (id, nombre, parent_id) VALUES (9001, 'repro', NULL) ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (9001, 9001, 0) ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO spec_definitions (categoria_raiz_id, spec_key, label, tipo) VALUES (9001, 'lens_mount', 'Montura', 'enum') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO equipo_fichas (equipo_id, montura) VALUES (9001, 'EF') ON CONFLICT (equipo_id) DO UPDATE SET montura = 'EF'")
        conn.commit()
    finally:
        conn.close()

    # Posicionar Alembic justo antes del backfill y correr toda la cadena.
    cfg = _alembic_config()
    command.stamp(cfg, "d7e9b3c5a8f2")  # down_revision de e8f4d9c2b1a3
    command.upgrade(cfg, "head")

    head = migration_state._head_revision(cfg)
    current = migration_state._current_revision()
    assert current == head, (
        f"Con datos legacy presentes, la cadena quedó en {current!r} pero el "
        f"head es {head!r} — una migración de backfill rompe sobre datos reales."
    )


def test_record_success_marca_ok(clean_db):
    """El módulo de visibilidad reporta `ok=True` cuando la BD está en el head."""
    from alembic import command
    from database import init_db
    import migration_state

    init_db()
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    migration_state.record_success(cfg)

    status = migration_state.get_status()
    assert status["checked"] is True
    assert status["ok"] is True
    assert status["current"] == status["head"]
    assert status["error"] is None
