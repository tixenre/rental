"""`routes.estudio.reorder_fotos` contra Postgres REAL — verifica el fix de
dead rows (2026-07-04): el editor de fotos del estudio manda el array
COMPLETO de fotos en cada drag, y el endpoint hacía un `UPDATE` por foto sin
comparar contra `orden`/`es_principal` ya guardados — mover UNA foto
reescribía TODAS. Mismo método de prueba (xmin) que los otros fixes de esta
auditoría; llama la función de la ruta directo (no HTTP) con
`ADMIN_BYPASS_AUTH=1`, mismo patrón que `test_kit_componentes_write_db.py`.

OPT-IN y SEGURO POR DEFECTO. Ids altos (9_600_5xx) + limpieza antes/después.
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

FA, FB = 9_600_501, 9_600_502


class FakeRequest:
    def __init__(self, cookies=None):
        self.cookies = cookies or {}


def _limpiar(conn):
    conn.execute("DELETE FROM estudio_fotos WHERE id IN (%s,%s)" % (FA, FB))


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("ADMIN_BYPASS_AUTH", "1")
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO estudio_fotos (id, estudio_id, url, orden, es_principal) VALUES "
            "(%s,1,%s,0,true),(%s,1,%s,1,false)",
            (FA, "https://x/a.jpg", FB, "https://x/b.jpg"),
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


def _filas(conn):
    rows = conn.execute(
        "SELECT id, orden, es_principal, xmin::text AS xmin FROM estudio_fotos "
        "WHERE id IN (%s,%s) ORDER BY id" % (FA, FB)
    ).fetchall()
    return {r["id"]: (r["orden"], r["es_principal"], r["xmin"]) for r in rows}


def test_reorder_con_el_mismo_orden_no_escribe_nada(setup):
    from database import get_db
    from routes.estudio import FotoOrdenItem, ReorderBody, reorder_fotos

    conn = get_db()
    try:
        antes = _filas(conn)

        # Mismo orden/es_principal que ya está guardado ⇒ no-op total.
        reorder_fotos(
            ReorderBody(fotos=[
                FotoOrdenItem(id=FA, orden=0, es_principal=True),
                FotoOrdenItem(id=FB, orden=1, es_principal=False),
            ]),
            FakeRequest(),
        )
        despues = _filas(conn)

        assert despues == antes
    finally:
        conn.close()


def test_reorder_mueve_solo_la_foto_que_cambio(setup):
    from database import get_db
    from routes.estudio import FotoOrdenItem, ReorderBody, reorder_fotos

    conn = get_db()
    try:
        antes = _filas(conn)

        # Solo FB cambia de orden (pasa a ser la principal); FA queda IGUAL.
        reorder_fotos(
            ReorderBody(fotos=[
                FotoOrdenItem(id=FA, orden=0, es_principal=True),
                FotoOrdenItem(id=FB, orden=1, es_principal=True),
            ]),
            FakeRequest(),
        )
        despues = _filas(conn)

        assert despues[FA] == antes[FA]  # sin cambios reales ⇒ mismo xmin
        assert despues[FB][1] is True
        assert despues[FB][2] != antes[FB][2]
    finally:
        conn.close()
