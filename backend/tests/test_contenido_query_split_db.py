"""`services.contenido.query_contenido_batch` + `shape_contenido_rows` contra
Postgres REAL — Fase 2 de la iniciativa de paralelización del catálogo
(issue #1240).

`contenido_de_batch` se partió en "armar SQL+params" (`query_contenido_batch`)
+ "dar forma a filas ya obtenidas" (`shape_contenido_rows`), para que un
caller con su propio pipeline de queries (ej. `proyectar_lista`) pueda
incluir esta consulta en el mismo lote sin reimplementar el SQL — la puerta
única sigue siendo la única fuente del SQL, solo se separó de su ejecución.

Verifica que la composición manual (query → conn.execute → shape) da
EXACTAMENTE el mismo resultado que `contenido_de_batch` de siempre — es un
refactor move-verbatim-y-separar, no debería cambiar ni un byte del output.

OPT-IN y SEGURO POR DEFECTO. Ids altos (9_600_9xx) + limpieza antes/después.
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

COMBO, COMP_A, COMP_B = 9_600_901, 9_600_902, 9_600_903


def _limpiar(conn):
    conn.execute("DELETE FROM kit_componentes WHERE equipo_id = %s" % COMBO)
    conn.execute("DELETE FROM equipos WHERE id IN (%s,%s,%s)" % (COMBO, COMP_A, COMP_B))


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute("INSERT INTO equipos (id, nombre, cantidad, tipo) VALUES (%s,%s,1,'combo')", (COMBO, "Combo split test"))
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,1)", (COMP_A, "Componente A"))
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,1)", (COMP_B, "Componente B"))
        conn.execute(
            "INSERT INTO kit_componentes (equipo_id, componente_id, cantidad, orden) VALUES (%s,%s,1,0),(%s,%s,1,1)",
            (COMBO, COMP_A, COMBO, COMP_B),
        )
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


def test_query_mas_shape_da_lo_mismo_que_contenido_de_batch(setup):
    from database import get_db
    from services.contenido import contenido_de_batch, query_contenido_batch, shape_contenido_rows

    conn = get_db()
    try:
        esperado = contenido_de_batch(conn, [COMBO])

        sql, params = query_contenido_batch([COMBO])
        rows = conn.execute(sql, params).fetchall()
        obtenido = shape_contenido_rows(rows, [COMBO])

        assert obtenido == esperado
        assert len(obtenido[COMBO]) == 2
        assert {c["componente_id"] for c in obtenido[COMBO]} == {COMP_A, COMP_B}
    finally:
        conn.close()


def test_query_contenido_batch_none_si_vacio():
    from services.contenido import query_contenido_batch

    assert query_contenido_batch([]) is None


def test_pipelined_select_puede_correr_la_query_de_contenido(setup):
    """Confirma que el SQL de query_contenido_batch es compatible con
    pipelined_select (Fase 1) — el caso real que usará proyectar_lista."""
    from database import get_db
    from services.contenido import contenido_de_batch, query_contenido_batch, shape_contenido_rows

    conn = get_db()
    try:
        sql, params = query_contenido_batch([COMBO])
        [rows] = conn.pipelined_select([(sql, params)])
        obtenido = shape_contenido_rows(rows, [COMBO])
        assert obtenido == contenido_de_batch(conn, [COMBO])
    finally:
        conn.close()
