"""#922 — el export de dataio es READ-ONLY (no muta esquema/datos).

Antes `export_equipos` corría un self-heal (`_ensure_equipos_slug`) que hacía
`ALTER TABLE` + `UPDATE` masivo + `ALTER ... ADD CONSTRAINT` + `commit()` en cada
"bajar backup" — un export, read-only por contrato, mutando esquema/datos (locks
en prod, commit incondicional). El backfill se movió a la fuente única
`dataio.slug.backfill_equipos_slug`, que corre en `init_db()` (bootstrap), en el
alta de equipo y en una migración Alembic.

Este test contra Postgres real verifica:
  1. `export_equipos` con un equipo de slug NULL NO lo puebla (read-only) — lo
     omite del export. La versión vieja lo poblaba (mutaba la base).
  2. `backfill_equipos_slug` sí lo puebla (el camino correcto), idempotente.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás *_db.py): se saltea salvo
`RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre. Trabaja
sobre ids altos (>= 9_400_000) y limpia al terminar.
"""
import os
from urllib.parse import urlparse

import pytest

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

EID = 9_400_001


@pytest.fixture
def equipo_sin_slug():
    """Inserta un equipo con slug NULL (idempotente) y limpia al terminar."""
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        conn.execute("DELETE FROM equipos WHERE id = %s", (EID,))
        conn.execute(
            "INSERT INTO equipos (id, nombre, modelo, cantidad, slug) VALUES (%s,%s,%s,%s,NULL)",
            (EID, "Equipo Sin Slug Test", "ZZ-922", 1),
        )
        conn.commit()
    finally:
        conn.close()

    yield

    conn = get_db()
    try:
        conn.execute("DELETE FROM equipos WHERE id = %s", (EID,))
        conn.commit()
    finally:
        conn.close()


def _slug_de(conn, eid):
    return conn.execute("SELECT slug FROM equipos WHERE id = %s", (eid,)).fetchone()["slug"]


def test_export_equipos_no_muta_slug(equipo_sin_slug):
    """El export NO puebla el slug NULL (read-only). El equipo se omite del
    resultado pero la base queda intacta."""
    from database import get_db
    from dataio.exporters import export_equipos

    conn = get_db()
    try:
        out = export_equipos(conn)
        # No aparece en el export (no tiene clave natural).
        assert all(e["nombre"] != "Equipo Sin Slug Test" for e in out)
        # Y la base NO fue mutada por el export.
        assert _slug_de(conn, EID) is None, "el export NO debe poblar el slug (read-only)"
    finally:
        conn.close()


def test_backfill_puebla_e_idempotente(equipo_sin_slug):
    """El camino correcto sí puebla el slug, y es idempotente."""
    from database import get_db
    from dataio.slug import backfill_equipos_slug

    conn = get_db()
    try:
        n = backfill_equipos_slug(conn)
        conn.commit()
        assert n >= 1
        slug = _slug_de(conn, EID)
        assert slug, "el backfill debe poblar el slug"
        # Segunda corrida: nada que poblar para este equipo (idempotente).
        backfill_equipos_slug(conn)
        conn.commit()
        assert _slug_de(conn, EID) == slug
    finally:
        conn.close()
