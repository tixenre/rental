"""`services.catalogo.proyeccion.proyectar_lista` — flag `incluir_detalle`
(2026-07-04): la tabla de búsqueda del admin (`equipos.index.lazy.tsx`) no lee
`kit`/`ficha`/`specs`/`specs_destacados` de cada fila (confirmado por grep
exhaustivo del componente) — solo nombre/marca/categoría/precio/stock/tipo. El
detalle de un equipo puntual sigue trayendo todo completo vía `proyectar_uno`
(GET /equipos/{id}), sin cambios. `incluir_detalle=False` saltea attach_kit/
attach_ficha/specs; el precio efectivo de combo NO se salta (no depende de
attach_kit — lee `kit_componentes` directo) para que un combo siga mostrando
su precio derivado, no 0.

El catálogo público SIEMPRE ignora el flag (lo fuerza el route, no
`proyectar_lista`) — filtra/rankea por specs y kit client-side.

OPT-IN y SEGURO POR DEFECTO. Ids altos (9_600_7xx) + limpieza antes/después.
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

CAT = 9_600_701
EQ_PLAIN, EQ_COMBO, EQ_COMP = 9_600_711, 9_600_712, 9_600_713


@contextmanager
def _count_matching(monkeypatch, needle: str):
    from database.core import PGConnection

    counter = [0]
    orig = PGConnection.execute

    def _wrapped(self, sql, params=()):
        if needle in sql:
            counter[0] += 1
        return orig(self, sql, params)

    monkeypatch.setattr(PGConnection, "execute", _wrapped)
    try:
        yield counter
    finally:
        monkeypatch.setattr(PGConnection, "execute", orig)


def _limpiar(conn):
    conn.execute(
        "DELETE FROM kit_componentes WHERE equipo_id IN (%s,%s,%s)" % (EQ_PLAIN, EQ_COMBO, EQ_COMP)
    )
    conn.execute("DELETE FROM equipo_specs WHERE equipo_id IN (%s,%s,%s)" % (EQ_PLAIN, EQ_COMBO, EQ_COMP))
    conn.execute("DELETE FROM equipo_fichas WHERE equipo_id IN (%s,%s,%s)" % (EQ_PLAIN, EQ_COMBO, EQ_COMP))
    conn.execute(
        "DELETE FROM equipo_categorias WHERE equipo_id IN (%s,%s,%s)" % (EQ_PLAIN, EQ_COMBO, EQ_COMP)
    )
    conn.execute("DELETE FROM equipos WHERE id IN (%s,%s,%s)" % (EQ_PLAIN, EQ_COMBO, EQ_COMP))
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
            (CAT, "ZZ-IncluirDetalleTest", 10, None),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, visible_catalogo, tipo, precio_jornada) "
            "VALUES (%s,%s,1,1,'simple',0)",
            (EQ_PLAIN, "eq-plain-detalle-test"),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, visible_catalogo, tipo, precio_jornada) "
            "VALUES (%s,%s,1,1,'combo',0)",
            (EQ_COMBO, "eq-combo-detalle-test"),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, visible_catalogo, tipo, precio_jornada) "
            "VALUES (%s,%s,1,1,'simple',100)",
            (EQ_COMP, "eq-componente-detalle-test"),
        )
        conn.execute(
            "INSERT INTO kit_componentes (equipo_id, componente_id, cantidad, descuento_pct, orden) "
            "VALUES (%s,%s,2,0,0)",
            (EQ_COMBO, EQ_COMP),
        )
        conn.execute(
            "INSERT INTO equipo_fichas (equipo_id, descripcion) VALUES (%s,%s)",
            (EQ_PLAIN, "una descripción de prueba"),
        )
        conn.execute(
            "INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (%s,%s,0)",
            (EQ_PLAIN, CAT),
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


def test_incluir_detalle_false_saltea_kit_ficha_specs(setup, monkeypatch):
    from database import get_db
    from services.catalogo.proyeccion import proyectar_lista

    conn = get_db()
    try:
        with _count_matching(monkeypatch, "equipo_specs") as specs_counter, \
             _count_matching(monkeypatch, "equipo_fichas") as ficha_counter:
            resultado = proyectar_lista(
                conn,
                filtro_sql="FROM equipos e WHERE e.id = ANY(%s)",
                filtro_params=[[EQ_PLAIN, EQ_COMBO, EQ_COMP]],
                is_admin=True,
                incluir_detalle=False,
            )
        assert specs_counter[0] == 0, "no debería tocar equipo_specs con incluir_detalle=False"
        assert ficha_counter[0] == 0, "no debería tocar equipo_fichas con incluir_detalle=False"

        items = {e["id"]: e for e in resultado["items"]}
        assert "kit" not in items[EQ_COMBO]
        assert "ficha" not in items[EQ_PLAIN]
        assert "specs" not in items[EQ_PLAIN]
        assert "specs_destacados" not in items[EQ_PLAIN]
        # tipo/categorías SIEMPRE presentes — la tabla admin los usa para
        # identificar combos y mostrar la categoría.
        assert items[EQ_COMBO]["tipo"] == "combo"
        assert items[EQ_PLAIN]["categorias"][0]["nombre"] == "ZZ-IncluirDetalleTest"
    finally:
        conn.close()


def test_incluir_detalle_false_no_rompe_precio_combo(setup):
    """El precio efectivo de combo no depende de attach_kit — sin esto un
    combo mostraría precio_jornada=0 (crudo) en vez de 200 (2 x $100 comp)."""
    from database import get_db
    from services.catalogo.proyeccion import proyectar_lista

    conn = get_db()
    try:
        resultado = proyectar_lista(
            conn,
            filtro_sql="FROM equipos e WHERE e.id = ANY(%s)",
            filtro_params=[[EQ_COMBO]],
            is_admin=True,
            incluir_detalle=False,
        )
        combo = resultado["items"][0]
        assert combo["precio_jornada"] == 200
    finally:
        conn.close()


def test_incluir_detalle_true_default_trae_todo(setup):
    """Regresión: el default (sin pasar el flag) preserva el comportamiento
    de siempre — kit/ficha/specs completos, como antes de este cambio."""
    from database import get_db
    from services.catalogo.proyeccion import proyectar_lista

    conn = get_db()
    try:
        resultado = proyectar_lista(
            conn,
            filtro_sql="FROM equipos e WHERE e.id = ANY(%s)",
            filtro_params=[[EQ_PLAIN, EQ_COMBO]],
            is_admin=True,
        )
        items = {e["id"]: e for e in resultado["items"]}
        assert "kit" in items[EQ_COMBO]
        assert items[EQ_PLAIN]["ficha"]["descripcion"] == "una descripción de prueba"
        assert "specs" in items[EQ_PLAIN]
    finally:
        conn.close()


def test_route_publico_ignora_incluir_detalle(setup):
    """GET /equipos?incluir_detalle=false SIN sesión admin sigue trayendo
    todo — el catálogo público nunca puede bajar el detalle (filtra/rankea
    por specs y kit client-side)."""
    from fastapi.testclient import TestClient
    import main

    with TestClient(main.app) as client:
        r = client.get(
            "/api/equipos",
            params={"incluir_detalle": "false", "solo_visibles": "true"},
        )
    assert r.status_code == 200
    items = {e["id"]: e for e in r.json()["items"] if e["id"] in (EQ_PLAIN, EQ_COMBO)}
    if EQ_PLAIN in items:
        assert "specs" in items[EQ_PLAIN]
        assert "ficha" in items[EQ_PLAIN]
