"""`services.categorias.query_categorias_de_equipos` + `shape_categorias_de_equipos_rows`
contra Postgres REAL — Fase 3 de la iniciativa de paralelización del
catálogo (issue #1240). Mismo patrón que `test_contenido_query_split_db.py`
(Fase 2): `categorias_de_equipos` se partió en armar SQL+params / dar forma a
filas ya obtenidas, para que `proyectar_lista` la incluya en su pipeline sin
reimplementar el SQL. Move-verbatim — el resultado tiene que ser idéntico.

OPT-IN y SEGURO POR DEFECTO. Ids altos (9_601_0xx) + limpieza antes/después.
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

CAT_A, CAT_B = 9_601_001, 9_601_002
EQ = 9_601_011


def _limpiar(conn):
    conn.execute("DELETE FROM equipo_categorias WHERE equipo_id = %s" % EQ)
    conn.execute("DELETE FROM equipos WHERE id = %s" % EQ)
    conn.execute("DELETE FROM categorias WHERE id IN (%s,%s)" % (CAT_A, CAT_B))


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO categorias (id, nombre, prioridad, parent_id) VALUES (%s,%s,10,NULL),(%s,%s,20,NULL)",
            (CAT_A, "ZZ-CategoriasSplitA", CAT_B, "ZZ-CategoriasSplitB"),
        )
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,1)", (EQ, "eq-categorias-split-test"))
        conn.execute(
            "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (%s,%s,0),(%s,%s,1)",
            (EQ, CAT_A, EQ, CAT_B),
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


def test_query_mas_shape_da_lo_mismo_que_categorias_de_equipos(setup):
    from database import get_db
    from services.categorias import (
        categorias_de_equipos,
        query_categorias_de_equipos,
        shape_categorias_de_equipos_rows,
    )

    conn = get_db()
    try:
        esperado = categorias_de_equipos(conn, [EQ])

        sql, params = query_categorias_de_equipos([EQ])
        rows = conn.execute(sql, params).fetchall()
        obtenido = shape_categorias_de_equipos_rows(rows)

        assert obtenido == esperado
        assert [c["nombre"] for c in obtenido[EQ]] == ["ZZ-CategoriasSplitA", "ZZ-CategoriasSplitB"]
    finally:
        conn.close()


def test_query_categorias_de_equipos_none_si_vacio():
    from services.categorias import query_categorias_de_equipos

    assert query_categorias_de_equipos([]) is None


def test_pipelined_select_puede_correr_la_query_de_categorias(setup):
    from database import get_db
    from services.categorias import (
        categorias_de_equipos,
        query_categorias_de_equipos,
        shape_categorias_de_equipos_rows,
    )

    conn = get_db()
    try:
        sql, params = query_categorias_de_equipos([EQ])
        [rows] = conn.pipelined_select([(sql, params)])
        obtenido = shape_categorias_de_equipos_rows(rows)
        assert obtenido == categorias_de_equipos(conn, [EQ])
    finally:
        conn.close()
