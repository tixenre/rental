"""`services.catalogo.proyeccion.proyectar_lista` contra Postgres REAL —
verifica el fix de latencia (2026-07-04): `attach_specs_estructuradas` y
`attach_specs_destacados` pedían el MISMO JOIN (equipo_specs+spec_definitions+
categoria_spec_templates) para el mismo lote de ids, dos veces por cada
carga de catálogo (encontrado investigando por qué "buscar un equipo se
siente lento" — la causa real era la carga inicial del catálogo, no la
búsqueda). `proyectar_lista` ahora pide `get_equipo_specs_rows` una sola vez
y se lo pasa a las dos funciones.

Cuenta ejecuciones de SQL que tocan `equipo_specs` (no nombres de función —
evita el problema de bind time de `from x import y`) para probar que el
JOIN corre UNA sola vez, sin importar cuántos equipos haya en el lote.

OPT-IN y SEGURO POR DEFECTO. Ids altos (9_600_6xx) + limpieza antes/después.
"""
import os
from contextlib import contextmanager
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

CAT = 9_600_601
EQA, EQB = 9_600_611, 9_600_612


@contextmanager
def _count_specs_queries(monkeypatch):
    """Cuenta ejecuciones de cualquier query que toque `equipo_specs`."""
    from database.core import PGConnection

    counter = [0]
    orig = PGConnection.execute

    def _wrapped(self, sql, params=()):
        if "equipo_specs" in sql:
            counter[0] += 1
        return orig(self, sql, params)

    monkeypatch.setattr(PGConnection, "execute", _wrapped)
    try:
        yield counter
    finally:
        monkeypatch.setattr(PGConnection, "execute", orig)


def _limpiar(conn):
    conn.execute("DELETE FROM equipo_specs WHERE equipo_id IN (%s,%s)" % (EQA, EQB))
    conn.execute("DELETE FROM equipo_categorias WHERE equipo_id IN (%s,%s)" % (EQA, EQB))
    conn.execute("DELETE FROM equipos WHERE id IN (%s,%s)" % (EQA, EQB))
    conn.execute("DELETE FROM categorias WHERE id = %s", (CAT,))


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO categorias (id, nombre, prioridad, parent_id) VALUES (%s,%s,%s,%s)",
            (CAT, "ZZ-CatalogoSpecsDedupTest", 10, None),
        )
        for eid in (EQA, EQB):
            conn.execute(
                "INSERT INTO equipos (id, nombre, cantidad, visible_catalogo) VALUES (%s,%s,%s,1)",
                (eid, f"eq-specs-dedup-{eid}", 1),
            )
            conn.execute(
                "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (%s,%s,0)",
                (eid, CAT),
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


def test_proyectar_lista_pide_specs_una_sola_vez_para_todo_el_lote(setup, monkeypatch):
    from database import get_db
    from services.catalogo.proyeccion import proyectar_lista

    conn = get_db()
    try:
        with _count_specs_queries(monkeypatch) as counter:
            resultado = proyectar_lista(
                conn,
                filtro_sql="FROM equipos e WHERE e.id = ANY(%s)",
                filtro_params=[[EQA, EQB]],
                is_admin=True,
            )
        assert len(resultado["items"]) == 2
        # Antes del fix: 2 (attach_specs_estructuradas + attach_specs_destacados
        # pedían el JOIN por separado). Con el fix: 1, sin importar el tamaño del lote.
        assert counter[0] == 1, f"se esperaba 1 query a equipo_specs, hubo {counter[0]}"
    finally:
        conn.close()


def test_proyectar_uno_sigue_andando_solo_con_estructuradas(setup):
    """proyectar_uno NO llama a attach_specs_destacados — el default
    rows_by_equipo=None de attach_specs_estructuradas debe seguir andando solo."""
    from database import get_db
    from services.catalogo.proyeccion import proyectar_uno

    conn = get_db()
    try:
        equipo = proyectar_uno(conn, EQA)
        assert equipo is not None
        assert equipo["id"] == EQA
        assert "specs" in equipo
    finally:
        conn.close()
