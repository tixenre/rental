"""`services.catalogo.proyeccion.proyectar_uno` — extensión de la Fase 5 de
#1240 al detalle de un equipo puntual (ficha/categorías/specs/kit/fotos), a
pedido del dueño ("si se puede mejorar, se mejora"): los mismos 5 queries
independientes que antes se pedían secuenciales ahora van en un pipeline.

Verifica: (1) el pipeline se llama con las 5 queries batcheadas, (2) el
resultado es shape-idéntico al que daba el código secuencial de antes
(incluye `solo_activos=False` para kit — la ficha muestra componentes
soft-deleted, a diferencia del catálogo), (3) un equipo combo resuelve su
precio efectivo igual que siempre.

OPT-IN y SEGURO POR DEFECTO. Ids altos (9_601_3xx) + limpieza antes/después.
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

CAT = 9_601_301
EQ_COMBO, EQ_COMP_ACTIVO, EQ_COMP_RETIRADO = 9_601_311, 9_601_312, 9_601_313


def _limpiar(conn):
    conn.execute(
        "DELETE FROM kit_componentes WHERE equipo_id = %s" % EQ_COMBO
    )
    conn.execute("DELETE FROM equipo_fotos WHERE equipo_id = %s" % EQ_COMBO)
    conn.execute("DELETE FROM equipo_fichas WHERE equipo_id = %s" % EQ_COMBO)
    conn.execute(
        "DELETE FROM equipo_categorias WHERE equipo_id IN (%s,%s,%s)"
        % (EQ_COMBO, EQ_COMP_ACTIVO, EQ_COMP_RETIRADO)
    )
    conn.execute(
        "DELETE FROM equipos WHERE id IN (%s,%s,%s)" % (EQ_COMBO, EQ_COMP_ACTIVO, EQ_COMP_RETIRADO)
    )
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
            (CAT, "ZZ-ProyectarUnoPipelineTest"),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, tipo, precio_jornada) VALUES (%s,%s,1,'combo',0)",
            (EQ_COMBO, "eq-combo-detalle-test"),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada) VALUES (%s,%s,1,100)",
            (EQ_COMP_ACTIVO, "eq-componente-activo-test"),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, eliminado_at) VALUES (%s,%s,1,50,NOW())",
            (EQ_COMP_RETIRADO, "eq-componente-retirado-test"),
        )
        conn.execute(
            "INSERT INTO kit_componentes (equipo_id, componente_id, cantidad, descuento_pct, orden) "
            "VALUES (%s,%s,1,0,0),(%s,%s,1,0,1)",
            (EQ_COMBO, EQ_COMP_ACTIVO, EQ_COMBO, EQ_COMP_RETIRADO),
        )
        conn.execute(
            "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (%s,%s,0)",
            (EQ_COMBO, CAT),
        )
        conn.execute(
            "INSERT INTO equipo_fichas (equipo_id, descripcion) VALUES (%s,%s)",
            (EQ_COMBO, "descripción del combo de prueba"),
        )
        conn.execute(
            "INSERT INTO equipo_fotos (equipo_id, url, es_principal, orden) VALUES (%s,%s,true,0)",
            (EQ_COMBO, "https://example.com/foto.jpg"),
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


def test_proyectar_uno_pide_las_5_queries_en_un_pipeline(setup, monkeypatch):
    from database import get_db
    from database.core import PGConnection
    from services.catalogo.proyeccion import proyectar_uno

    llamadas = []
    orig = PGConnection.pipelined_select

    def _spy(self, queries):
        llamadas.append(queries)
        return orig(self, queries)

    monkeypatch.setattr(PGConnection, "pipelined_select", _spy)

    conn = get_db()
    try:
        equipo = proyectar_uno(conn, EQ_COMBO)
    finally:
        conn.close()

    assert equipo is not None
    assert len(llamadas) == 1, f"se esperaba 1 llamada a pipelined_select, hubo {len(llamadas)}"
    assert len(llamadas[0]) == 5
    tablas = {sql for sql, _ in llamadas[0]}
    assert any("equipo_fichas" in s for s in tablas)
    assert any("equipo_categorias" in s for s in tablas)
    assert any("equipo_specs" in s for s in tablas)
    assert any("kit_componentes" in s for s in tablas)
    assert any("equipo_fotos" in s for s in tablas)


def test_proyectar_uno_shape_correcto(setup):
    from database import get_db
    from services.catalogo.proyeccion import proyectar_uno

    conn = get_db()
    try:
        equipo = proyectar_uno(conn, EQ_COMBO)
    finally:
        conn.close()

    assert equipo["id"] == EQ_COMBO
    assert equipo["ficha"]["descripcion"] == "descripción del combo de prueba"
    assert equipo["categorias"][0]["nombre"] == "ZZ-ProyectarUnoPipelineTest"
    assert equipo["fotos"] == [{"url": "https://example.com/foto.jpg", "es_principal": True}]

    # solo_activos=False: la ficha de UN equipo muestra el componente
    # retirado (soft-deleted) también — a diferencia del catálogo/listado.
    kit_ids = {c["componente_id"] for c in equipo["kit"]}
    assert kit_ids == {EQ_COMP_ACTIVO, EQ_COMP_RETIRADO}
    # Mismo shape que attach_kit (reusado, no reconstruido inline).
    assert set(equipo["kit"][0].keys()) == {
        "componente_id", "nombre", "marca", "foto_url", "cantidad", "descuento_pct", "esencial",
    }

    # Combo: precio efectivo derivado de componentes, no el crudo (0).
    # precio_combo excluye el componente retirado (eliminado_at IS NOT NULL)
    # de la CUENTA — a diferencia del kit para MOSTRAR, que sí lo incluye
    # (misma asimetría documentada en services/services/contenido).
    assert equipo["precio_jornada"] == 100


def test_proyectar_uno_inexistente_devuelve_none():
    from database import get_db
    from services.catalogo.proyeccion import proyectar_uno

    conn = get_db()
    try:
        assert proyectar_uno(conn, 999_999_999) is None
    finally:
        conn.close()
