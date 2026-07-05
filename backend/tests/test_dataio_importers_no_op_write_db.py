"""`dataio.importers.import_marcas`/`import_equipos` contra Postgres REAL —
verifica el fix de dead rows (2026-07-04): re-importar el MISMO JSON dos veces
(el patrón real de un `dataio import` para clonar/restaurar un ambiente, ver
`docs/DECISIONES.md` 2026-06-20) hacía un `UPDATE`/upsert incondicional en
cada fila del batch, aunque el valor ya fuera idéntico al guardado — mismo
patrón de bug que ya se arregló hoy en `nombre_service`/`asignar_categorias`/
`kit.py`. Acá el guard vive en el propio SQL (`WHERE (...) IS DISTINCT FROM
(...)` sobre la fila completa sujeta a EXCLUDED), no en Python — necesario
porque es un `ON CONFLICT DO UPDATE` con `RETURNING`.

Nota de semántica de Postgres (confirmada a mano): cuando el WHERE del
`DO UPDATE` no matchea, `RETURNING` NO devuelve fila — `import_equipos` usa el
`id` devuelto para sincronizar categorías, así que ahora cae a
`resolver.equipo_id(slug)` en ese caso (el equipo ya existía antes del batch,
así que ya está en el cache lazy del resolver).

Mismo método de prueba (xmin) que los otros 3 fixes de esta auditoría.

OPT-IN y SEGURO POR DEFECTO. Ids altos (9_600_4xx) + limpieza antes/después.
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

MARCA = "ZZ-DataioNoOpTest"
SLUG = "zz-dataio-noop-test-9600401"


def _limpiar(conn):
    conn.execute("DELETE FROM equipos WHERE slug = %s", (SLUG,))
    conn.execute("DELETE FROM marcas WHERE nombre = %s", (MARCA,))


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.commit()
    finally:
        conn.close()
    yield
    conn = get_db()
    try:
        _limpiar(conn)
        conn.commit()
    finally:
        conn.close()


def _xmin_marca(conn):
    r = conn.execute("SELECT xmin::text AS xmin FROM marcas WHERE nombre=%s", (MARCA,)).fetchone()
    return r["xmin"]


def _xmin_equipo(conn):
    r = conn.execute("SELECT id, xmin::text AS xmin FROM equipos WHERE slug=%s", (SLUG,)).fetchone()
    return r["id"], r["xmin"]


def test_reimportar_la_misma_marca_no_escribe(setup):
    from database import get_db
    from dataio.importers import import_marcas
    from dataio.natural_keys import KeyResolver

    conn = get_db()
    try:
        row = {"nombre": MARCA, "logo_url": "https://x/logo.png", "visible": True, "orden": 50, "destacada": False}
        resolver = KeyResolver(conn)

        stats1 = import_marcas(conn, [row], resolver)
        conn.commit()
        assert stats1["inserted"] == 1
        xmin_antes = _xmin_marca(conn)

        # Re-import del MISMO JSON (el caso real: export→import de un backup) ⇒ no-op.
        resolver2 = KeyResolver(conn)
        stats2 = import_marcas(conn, [row], resolver2)
        conn.commit()

        assert stats2["skipped"] == 1
        assert stats2["updated"] == 0
        assert _xmin_marca(conn) == xmin_antes
    finally:
        conn.close()


def test_reimportar_marca_con_un_campo_distinto_si_escribe(setup):
    from database import get_db
    from dataio.importers import import_marcas
    from dataio.natural_keys import KeyResolver

    conn = get_db()
    try:
        row = {"nombre": MARCA, "logo_url": "https://x/logo.png", "visible": True, "orden": 50, "destacada": False}
        import_marcas(conn, [row], KeyResolver(conn))
        conn.commit()
        xmin_antes = _xmin_marca(conn)

        row2 = {**row, "orden": 99}
        stats2 = import_marcas(conn, [row2], KeyResolver(conn))
        conn.commit()

        assert stats2["updated"] == 1
        assert _xmin_marca(conn) != xmin_antes
    finally:
        conn.close()


def test_reimportar_el_mismo_equipo_no_escribe_y_resuelve_id(setup):
    from database import get_db
    from dataio.importers import import_equipos
    from dataio.natural_keys import KeyResolver

    conn = get_db()
    try:
        row = {
            "slug": SLUG, "nombre": "Equipo dataio no-op test", "marca_nombre": None,
            "modelo": "X1", "cantidad": 1, "categorias": [],
        }
        resolver = KeyResolver(conn)
        stats1 = import_equipos(conn, [row], resolver)
        conn.commit()
        assert stats1["inserted"] == 1
        equipo_id_antes, xmin_antes = _xmin_equipo(conn)

        # Re-import idéntico ⇒ no-op, pero el id sigue resolviéndose bien
        # (necesario para el sync de categorías que corre después en el loop real).
        resolver2 = KeyResolver(conn)
        stats2 = import_equipos(conn, [row], resolver2)
        conn.commit()

        assert stats2["skipped"] == 1
        assert stats2["updated"] == 0
        equipo_id_despues, xmin_despues = _xmin_equipo(conn)
        assert equipo_id_despues == equipo_id_antes
        assert xmin_despues == xmin_antes
    finally:
        conn.close()
