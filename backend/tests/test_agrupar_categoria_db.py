"""Agrupación por categoría RAÍZ (sector) contra Postgres REAL (#814 / root-grouping).

La parte pura (`_ordenar_items_en_grupos`) ya está testeada sin DB en
`test_agrupar_categoria.py`. Acá se ejerce la parte SQL —`_agrupar_items_por_categoria`—
que resuelve, por equipo, la categoría RAÍZ de su primera categoría trepando por
`parent_id`. Verifica que un equipo asignado a una hija o a una NIETA caiga bajo
su sector raíz (no bajo la hoja), y que los grupos se ordenen por la `prioridad`
de la raíz.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los otros *_db.py): se saltea salvo
`RESERVAS_DB_TEST=1` + `DATABASE_URL` con 'test' en el nombre. Ids altos + limpieza.
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

# Ids altos para no chocar con datos reales.
C_ROOT_CAM, C_HIJA_VIDEO, C_NIETA_CINE = 9_400_001, 9_400_002, 9_400_003
C_ROOT_LENTES, C_HIJA_ZOOM = 9_400_011, 9_400_012
C_ROOT_LUZ = 9_400_021
ALL_CAT = (C_ROOT_CAM, C_HIJA_VIDEO, C_NIETA_CINE, C_ROOT_LENTES, C_HIJA_ZOOM, C_ROOT_LUZ)

EQ_NIETA, EQ_HIJA, EQ_RAIZ, EQ_SIN = 9_400_101, 9_400_102, 9_400_103, 9_400_104
ALL_EQ = (EQ_NIETA, EQ_HIJA, EQ_RAIZ, EQ_SIN)


def _limpiar(conn):
    conn.execute("DELETE FROM equipo_categorias WHERE equipo_id IN %s" % (ALL_EQ,))
    conn.execute("DELETE FROM equipos WHERE id IN %s" % (ALL_EQ,))
    conn.execute("DELETE FROM categorias WHERE id IN %s" % (ALL_CAT,))


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        # Árbol: Cámaras(raíz, prio 10) → Video(hija) → Cine(nieta);
        #        Lentes(raíz, prio 20) → Zoom(hija); Iluminación(raíz, prio 30).
        conn.execute(
            "INSERT INTO categorias (id, nombre, prioridad, parent_id) VALUES "
            "(%s,%s,%s,%s),(%s,%s,%s,%s),(%s,%s,%s,%s),(%s,%s,%s,%s),(%s,%s,%s,%s),(%s,%s,%s,%s)",
            (
                C_ROOT_CAM, "ZZ-Cámaras-test", 10, None,
                C_HIJA_VIDEO, "ZZ-Video-test", 10, C_ROOT_CAM,
                C_NIETA_CINE, "ZZ-Cine-test", 10, C_HIJA_VIDEO,
                C_ROOT_LENTES, "ZZ-Lentes-test", 20, None,
                C_HIJA_ZOOM, "ZZ-Zoom-test", 20, C_ROOT_LENTES,
                C_ROOT_LUZ, "ZZ-Iluminación-test", 30, None,
            ),
        )
        for eq in ALL_EQ:
            conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (%s,%s,%s)", (eq, f"eq-{eq}", 1))
        # EQ_NIETA → nieta (Cine) ⇒ raíz Cámaras
        # EQ_HIJA  → hija (Zoom)  ⇒ raíz Lentes
        # EQ_RAIZ  → raíz directa (Iluminación)
        # EQ_SIN   → sin categoría ⇒ 'Otros'
        conn.execute("INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (%s,%s,0)", (EQ_NIETA, C_NIETA_CINE))
        conn.execute("INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (%s,%s,0)", (EQ_HIJA, C_HIJA_ZOOM))
        conn.execute("INSERT INTO equipo_categorias (equipo_id, categoria_id, orden) VALUES (%s,%s,0)", (EQ_RAIZ, C_ROOT_LUZ))
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


def test_agrupa_por_raiz_trepando_hija_y_nieta(setup):
    from database import get_db
    from routes.alquileres import _agrupar_items_por_categoria

    items = [
        {"equipo_id": EQ_NIETA, "nombre": "a"},
        {"equipo_id": EQ_HIJA, "nombre": "b"},
        {"equipo_id": EQ_RAIZ, "nombre": "c"},
        {"equipo_id": EQ_SIN, "nombre": "d"},
        {"equipo_id": None, "nombre_libre": "Flete"},
    ]
    conn = get_db()
    try:
        grupos = _agrupar_items_por_categoria(conn, items)
    finally:
        conn.close()

    nombres = [g["categoria"] for g in grupos]
    # Ordenados por prioridad de la RAÍZ; 'Otros' último.
    assert nombres == ["ZZ-Cámaras-test", "ZZ-Lentes-test", "ZZ-Iluminación-test", "Otros"]
    # La nieta cayó bajo su raíz (Cámaras), no bajo 'Cine'.
    assert grupos[0]["items"][0]["equipo_id"] == EQ_NIETA
    # La hija cayó bajo su raíz (Lentes), no bajo 'Zoom'.
    assert grupos[1]["items"][0]["equipo_id"] == EQ_HIJA
    # Sin categoría + línea libre → 'Otros'.
    otros_ids = {i.get("equipo_id") for i in grupos[-1]["items"]}
    assert EQ_SIN in otros_ids and None in otros_ids
