"""`database.core.PGConnection.pipelined_select` contra Postgres REAL —
Fase 1 de la iniciativa de paralelización del catálogo (issue #1240).

Verifica la semántica real del pipeline mode de psycopg3 (no se puede probar
con un fake — es un comportamiento del protocolo, no de Python):
  1. Los resultados vuelven en el MISMO orden que las queries de entrada,
     aunque psycopg3 las despache sin esperar cada round-trip.
  2. El contenido es IDÉNTICO a correr las mismas queries secuencialmente
     (mismo `execute()`+`fetchall()` de siempre, uno por uno).
  3. Si UNA query del lote falla, TODAS fallan juntas (semántica de pipeline
     de Postgres — confirmado a mano antes de escribir el helper) y la
     conexión queda utilizable después de un rollback (mismo patrón que
     `PGConnection.close()` ya hace al devolver al pool).

OPT-IN y SEGURO POR DEFECTO. No muta nada — solo lee tablas ya sembradas por
`init_db()` (categorias/equipos si existen, o un universo chico propio).
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

CAT_A, CAT_B, CAT_C = 9_600_801, 9_600_802, 9_600_803


def _limpiar(conn):
    conn.execute("DELETE FROM categorias WHERE id IN (%s,%s,%s)" % (CAT_A, CAT_B, CAT_C))


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO categorias (id, nombre, prioridad, parent_id) VALUES "
            "(%s,%s,10,NULL),(%s,%s,20,NULL),(%s,%s,30,NULL)",
            (CAT_A, "ZZ-Pipeline-A", CAT_B, "ZZ-Pipeline-B", CAT_C, "ZZ-Pipeline-C"),
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


def test_resultados_en_el_mismo_orden_que_las_queries(setup):
    from database import get_db

    conn = get_db()
    try:
        resultados = conn.pipelined_select([
            ("SELECT nombre FROM categorias WHERE id = %s", (CAT_C,)),
            ("SELECT nombre FROM categorias WHERE id = %s", (CAT_A,)),
            ("SELECT nombre FROM categorias WHERE id = %s", (CAT_B,)),
        ])
        assert [r[0]["nombre"] for r in resultados] == [
            "ZZ-Pipeline-C", "ZZ-Pipeline-A", "ZZ-Pipeline-B",
        ]
    finally:
        conn.close()


def test_mismo_resultado_que_secuencial(setup):
    from database import get_db

    conn = get_db()
    try:
        queries = [
            ("SELECT id, nombre FROM categorias WHERE id = ANY(%s) ORDER BY id", ([CAT_A, CAT_B, CAT_C],)),
            ("SELECT count(*) AS n FROM categorias WHERE prioridad >= %s", (10,)),
        ]
        pipelined = conn.pipelined_select(queries)

        secuencial = []
        for sql, params in queries:
            secuencial.append([dict(zip(r.keys(), r.data)) for r in conn.execute(sql, params).fetchall()])

        pipelined_as_dicts = [[dict(zip(r.keys(), r.data)) for r in grupo] for grupo in pipelined]
        assert pipelined_as_dicts == secuencial
    finally:
        conn.close()


def test_una_query_rota_hace_fallar_todo_el_lote(setup):
    from database import get_db

    conn = get_db()
    try:
        with pytest.raises(Exception):
            conn.pipelined_select([
                ("SELECT nombre FROM categorias WHERE id = %s", (CAT_A,)),
                ("SELECT * FROM tabla_inexistente_zz", ()),
            ])
        # Mismo patrón que ya usa PGConnection.close(): un rollback deja la
        # conexión utilizable de nuevo (no hace falta nada más del caller).
        conn.rollback()
        row = conn.execute("SELECT nombre FROM categorias WHERE id = %s", (CAT_A,)).fetchone()
        assert row["nombre"] == "ZZ-Pipeline-A"
    finally:
        conn.close()


def test_una_sola_query_funciona_igual_que_execute(setup):
    from database import get_db

    conn = get_db()
    try:
        resultados = conn.pipelined_select([
            ("SELECT nombre FROM categorias WHERE id = %s", (CAT_B,)),
        ])
        assert len(resultados) == 1
        assert resultados[0][0]["nombre"] == "ZZ-Pipeline-B"
    finally:
        conn.close()
