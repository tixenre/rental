"""`query_ficha_batch`/`shape_ficha_rows` (database/equipos.py) y
`query_equipo_specs_rows`/`shape_equipo_specs_rows` (services/specs) contra
Postgres REAL — Fase 4 de la iniciativa de paralelización del catálogo
(issue #1240). Mismo patrón que las Fases 2/3 (contenido, categorias): ambos
ya eran SQL directo (sin cruzar ninguna puerta única), se partieron en
armar SQL+params / dar forma a filas ya obtenidas, para que `proyectar_lista`
los incluya en su pipeline. Move-verbatim — el resultado tiene que ser
idéntico a `attach_ficha`/`get_equipo_specs_rows` de siempre.

OPT-IN y SEGURO POR DEFECTO. Ids altos (9_601_1xx) + limpieza antes/después.
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

CAT = 9_601_101
EQ_CON_FICHA, EQ_SIN_FICHA = 9_601_111, 9_601_112


def _limpiar(conn):
    conn.execute("DELETE FROM equipo_specs WHERE equipo_id IN (%s,%s)" % (EQ_CON_FICHA, EQ_SIN_FICHA))
    conn.execute("DELETE FROM equipo_fichas WHERE equipo_id IN (%s,%s)" % (EQ_CON_FICHA, EQ_SIN_FICHA))
    conn.execute("DELETE FROM equipo_categorias WHERE equipo_id IN (%s,%s)" % (EQ_CON_FICHA, EQ_SIN_FICHA))
    conn.execute("DELETE FROM equipos WHERE id IN (%s,%s)" % (EQ_CON_FICHA, EQ_SIN_FICHA))
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
            (CAT, "ZZ-FichaSpecsSplitTest"),
        )
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,1)", (EQ_CON_FICHA, "eq-con-ficha"))
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,1)", (EQ_SIN_FICHA, "eq-sin-ficha"))
        conn.execute(
            "INSERT INTO equipo_fichas (equipo_id, descripcion) VALUES (%s,%s)",
            (EQ_CON_FICHA, "una descripción de prueba"),
        )
        conn.execute(
            "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (%s,%s,0),(%s,%s,0)",
            (EQ_CON_FICHA, CAT, EQ_SIN_FICHA, CAT),
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


def test_ficha_split_da_lo_mismo_que_attach_ficha(setup):
    from database import attach_ficha, query_ficha_batch, shape_ficha_rows
    from database import get_db

    conn = get_db()
    try:
        ids = [EQ_CON_FICHA, EQ_SIN_FICHA]
        equipos = [{"id": eid} for eid in ids]
        esperado = attach_ficha(conn, [dict(e) for e in equipos])

        sql, params = query_ficha_batch(ids)
        rows = conn.execute(sql, params).fetchall()
        ficha_map = shape_ficha_rows(rows, ids)

        for e in esperado:
            assert ficha_map[e["id"]] == e["ficha"]
        assert ficha_map[EQ_CON_FICHA]["descripcion"] == "una descripción de prueba"
        assert ficha_map[EQ_SIN_FICHA]["descripcion"] is None
    finally:
        conn.close()


def test_query_ficha_batch_none_si_vacio():
    from database import query_ficha_batch

    assert query_ficha_batch([]) is None


def test_pipelined_select_puede_correr_la_query_de_ficha(setup):
    from database import attach_ficha, get_db, query_ficha_batch, shape_ficha_rows

    conn = get_db()
    try:
        ids = [EQ_CON_FICHA]
        sql, params = query_ficha_batch(ids)
        [rows] = conn.pipelined_select([(sql, params)])
        ficha_map = shape_ficha_rows(rows, ids)

        esperado = attach_ficha(conn, [{"id": EQ_CON_FICHA}])[0]["ficha"]
        assert ficha_map[EQ_CON_FICHA] == esperado
    finally:
        conn.close()


def test_specs_split_da_lo_mismo_que_get_equipo_specs_rows(setup):
    """Spec sintético armado directo (spec_definitions + categoria_spec_templates
    + equipo_specs) — NO vía el seeder del registry, que exige que el nombre
    matchee una categoría REAL del registry Python (gotcha documentado en
    services/specs/CLAUDE.md Fase 4); acá solo hace falta *algún* spec para
    comparar los dos caminos, no una categoría real."""
    from database import get_db

    conn = get_db()
    try:
        spec_def_id = conn.insert_returning(
            "INSERT INTO spec_definitions (categoria_raiz_id, spec_key, label, tipo, prioridad, favorito, en_filtros) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (CAT, "zz_spec_split", "ZZ Spec Split", "string", 10, True, True),
        )
        conn.execute(
            "INSERT INTO categoria_spec_templates (categoria_id, spec_def_id) VALUES (%s,%s)",
            (CAT, spec_def_id),
        )
        conn.execute(
            "INSERT INTO equipo_specs (equipo_id, spec_def_id, value) VALUES (%s,%s,%s)",
            (EQ_CON_FICHA, spec_def_id, "un valor"),
        )
        conn.commit()

        from services.specs import get_equipo_specs_rows, query_equipo_specs_rows, shape_equipo_specs_rows

        ids = [EQ_CON_FICHA, EQ_SIN_FICHA]
        esperado = get_equipo_specs_rows(conn, ids)

        sql, params = query_equipo_specs_rows(ids)
        rows = conn.execute(sql, params).fetchall()
        obtenido = shape_equipo_specs_rows(rows, ids)

        assert obtenido == esperado
        assert len(obtenido[EQ_CON_FICHA]) == 1
        assert obtenido[EQ_CON_FICHA][0]["value"] == "un valor"
        assert obtenido[EQ_SIN_FICHA] == []
    finally:
        conn.execute("DELETE FROM equipo_specs WHERE equipo_id = %s" % EQ_CON_FICHA)
        conn.execute("DELETE FROM categoria_spec_templates WHERE categoria_id = %s" % CAT)
        conn.execute("DELETE FROM spec_definitions WHERE categoria_raiz_id = %s" % CAT)
        conn.commit()
        conn.close()


def test_query_equipo_specs_rows_none_si_vacio():
    from services.specs import query_equipo_specs_rows

    assert query_equipo_specs_rows([]) is None
