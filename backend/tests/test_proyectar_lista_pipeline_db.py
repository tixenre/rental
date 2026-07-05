"""`services.catalogo.proyeccion.proyectar_lista` — Fase 5 de #1240: los 4
attaches independientes (categorías + kit/ficha/specs si `incluir_detalle`)
ahora se piden en UN solo `pipelined_select`, no en 4 llamadas secuenciales
a `conn.execute`. Verifica el "cableado" en sí (que la llamada al pipeline
ocurra, con las queries esperadas adentro) — la corrección de cada query
individual ya está cubierta por las Fases 2-4 (test_contenido_query_split_db.py,
test_categorias_query_split_db.py, test_ficha_specs_query_split_db.py) y por
`test_catalogo_incluir_detalle_db.py`/`test_catalogo_specs_dedup_db.py`
(shape del resultado final).

OPT-IN y SEGURO POR DEFECTO. Ids altos (9_601_2xx) + limpieza antes/después.
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

CAT = 9_601_201
EQ = 9_601_211


def _limpiar(conn):
    conn.execute("DELETE FROM equipo_categorias WHERE equipo_id = %s" % EQ)
    conn.execute("DELETE FROM equipos WHERE id = %s" % EQ)
    conn.execute("DELETE FROM categorias WHERE id = %s", (CAT,))


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO categorias (id, nombre, prioridad, parent_id) VALUES (%s,%s,10,NULL)",
            (CAT, "ZZ-PipelineWireTest"),
        )
        conn.execute("INSERT INTO equipos (id, nombre, cantidad, visible_catalogo) VALUES (%s,%s,1,1)", (EQ, "eq-pipeline-wire-test"))
        conn.execute("INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (%s,%s,0)", (EQ, CAT))
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


def test_incluir_detalle_true_pide_las_4_queries_en_un_pipeline(setup, monkeypatch):
    from database import get_db
    from database.core import PGConnection
    from services.catalogo.proyeccion import proyectar_lista

    llamadas = []
    orig = PGConnection.pipelined_select

    def _spy(self, queries):
        llamadas.append(queries)
        return orig(self, queries)

    monkeypatch.setattr(PGConnection, "pipelined_select", _spy)

    conn = get_db()
    try:
        proyectar_lista(
            conn,
            filtro_sql="FROM equipos e WHERE e.id = ANY(%s)",
            filtro_params=[[EQ]],
            is_admin=True,
        )
    finally:
        conn.close()

    assert len(llamadas) == 1, f"se esperaba 1 llamada a pipelined_select, hubo {len(llamadas)}"
    tablas_tocadas = {sql for sql, _ in llamadas[0]}
    assert any("equipo_categorias" in s for s in tablas_tocadas)
    assert any("kit_componentes" in s for s in tablas_tocadas)
    assert any("equipo_fichas" in s for s in tablas_tocadas)
    assert any("equipo_specs" in s for s in tablas_tocadas)
    assert len(llamadas[0]) == 4


def test_incluir_detalle_false_pide_solo_categorias_en_el_pipeline(setup, monkeypatch):
    from database import get_db
    from database.core import PGConnection
    from services.catalogo.proyeccion import proyectar_lista

    llamadas = []
    orig = PGConnection.pipelined_select

    def _spy(self, queries):
        llamadas.append(queries)
        return orig(self, queries)

    monkeypatch.setattr(PGConnection, "pipelined_select", _spy)

    conn = get_db()
    try:
        proyectar_lista(
            conn,
            filtro_sql="FROM equipos e WHERE e.id = ANY(%s)",
            filtro_params=[[EQ]],
            is_admin=True,
            incluir_detalle=False,
        )
    finally:
        conn.close()

    assert len(llamadas) == 1
    assert len(llamadas[0]) == 1
    sql, _ = llamadas[0][0]
    assert "equipo_categorias" in sql
