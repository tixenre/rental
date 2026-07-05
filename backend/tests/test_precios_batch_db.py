"""`precios_efectivos_batch` (`services/precios.py`) + el gate en lote de
`services/carrito/readiness.py` — contra Postgres REAL.

Optimiza el N+1 documentado en `docs/SISTEMA_FINANZAS_FLUJO.md` (hallazgo #12):
`precios_catalogo_para_reserva` (creación real de pedido del cliente) resolvía
el gate de visibilidad + el precio de cada ítem del carrito UNO POR UNO. Ahora
son 2 queries totales (`= ANY(%s)`, no un `IN (...)` armado a mano — el patrón
que #643 revirtió en `/api/cotizar` por devolver el mapa de precios vacío en
prod). Este test verifica que el resultado en lote es BYTE-IDÉNTICO al
resultado ítem-por-ítem (`precio_jornada_efectivo`), para un mix de equipos
simples + un combo — el caso donde un bug de agrupamiento sería más fácil de
esconder.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás `*_db.py`).
"""
import os
from types import SimpleNamespace
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
        not _OPT_IN, reason="opt-in: setear RESERVAS_DB_TEST=1 + DATABASE_URL a una base de prueba"
    ),
    pytest.mark.skipif(
        _OPT_IN and not _looks_like_test_db(),
        reason=f"DATABASE_URL ({_DB_NAME!r}) no parece base de test — abortado por seguridad",
    ),
]

EQ_SIMPLE_A = 9_360_201
EQ_SIMPLE_B = 9_360_202
EQ_COMBO = 9_360_203
EQ_COMP_A = 9_360_204
EQ_COMP_B = 9_360_205
EQ_OCULTO = 9_360_206  # visible_catalogo = 0 — no debe pasar el gate
EQ_INEXISTENTE = 9_360_299  # nunca se inserta


def _limpiar(conn):
    conn.execute("DELETE FROM kit_componentes WHERE equipo_id = %s", (EQ_COMBO,))
    conn.execute(
        "DELETE FROM equipos WHERE id IN (%s,%s,%s,%s,%s,%s)",
        (EQ_SIMPLE_A, EQ_SIMPLE_B, EQ_COMBO, EQ_COMP_A, EQ_COMP_B, EQ_OCULTO),
    )


@pytest.fixture
def conn():
    from database import get_db, init_db

    init_db()
    c = get_db()
    try:
        _limpiar(c)
        c.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo, tipo) "
            "VALUES (%s,'Simple A batch-test',5,12000,1,'simple')",
            (EQ_SIMPLE_A,),
        )
        c.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo, tipo) "
            "VALUES (%s,'Simple B batch-test',5,7500,1,'simple')",
            (EQ_SIMPLE_B,),
        )
        c.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo, tipo) "
            "VALUES (%s,'Componente A batch-test',5,5000,1,'simple')",
            (EQ_COMP_A,),
        )
        c.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo, tipo) "
            "VALUES (%s,'Componente B batch-test',5,5000,1,'simple')",
            (EQ_COMP_B,),
        )
        c.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo, tipo) "
            "VALUES (%s,'Combo batch-test',5,0,1,'combo')",
            (EQ_COMBO,),
        )
        c.execute(
            "INSERT INTO kit_componentes (equipo_id, componente_id, cantidad, descuento_pct) "
            "VALUES (%s,%s,1,10), (%s,%s,1,0)",
            (EQ_COMBO, EQ_COMP_A, EQ_COMBO, EQ_COMP_B),
        )
        # precio_combo = 5000*0.9 + 5000*1.0 = 9500
        c.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo, tipo) "
            "VALUES (%s,'Oculto batch-test',5,9999,0,'simple')",
            (EQ_OCULTO,),
        )
        c.commit()
        yield c
    finally:
        _limpiar(c)
        c.commit()
        c.close()


def test_precios_efectivos_batch_coincide_con_resolucion_item_por_item(conn):
    from services.precios import precio_jornada_efectivo, precios_efectivos_batch

    ids = [EQ_SIMPLE_A, EQ_SIMPLE_B, EQ_COMBO]
    batch = precios_efectivos_batch(conn, ids)
    esperado = {i: precio_jornada_efectivo(conn, i) for i in ids}

    assert batch == esperado
    assert batch[EQ_SIMPLE_A] == 12000
    assert batch[EQ_SIMPLE_B] == 7500
    assert batch[EQ_COMBO] == 9500  # derivado de sus componentes, no su precio_jornada=0


def test_precios_efectivos_batch_ignora_id_inexistente(conn):
    from services.precios import precios_efectivos_batch

    batch = precios_efectivos_batch(conn, [EQ_SIMPLE_A, EQ_INEXISTENTE])
    assert batch == {EQ_SIMPLE_A: 12000}  # el inexistente no aparece, no explota


def test_precios_efectivos_batch_lista_vacia():
    from services.precios import precios_efectivos_batch

    assert precios_efectivos_batch(None, []) == {}  # short-circuit, ni toca conn


def test_precios_catalogo_para_reserva_resuelve_mix_simple_y_combo(conn):
    from services.carrito.readiness import precios_catalogo_para_reserva

    items = [
        SimpleNamespace(equipo_id=EQ_SIMPLE_A),
        SimpleNamespace(equipo_id=EQ_COMBO),
        SimpleNamespace(equipo_id=EQ_SIMPLE_A),  # duplicado — se dedup, no rompe
    ]
    precios = precios_catalogo_para_reserva(conn, items)
    assert precios == {EQ_SIMPLE_A: 12000, EQ_COMBO: 9500}


def test_precios_catalogo_para_reserva_rechaza_equipo_oculto(conn):
    from fastapi import HTTPException

    from services.carrito.readiness import precios_catalogo_para_reserva

    items = [SimpleNamespace(equipo_id=EQ_SIMPLE_A), SimpleNamespace(equipo_id=EQ_OCULTO)]
    with pytest.raises(HTTPException) as exc:
        precios_catalogo_para_reserva(conn, items)
    assert exc.value.status_code == 404
    assert str(EQ_OCULTO) in exc.value.detail


def test_precios_catalogo_para_reserva_rechaza_equipo_inexistente(conn):
    from fastapi import HTTPException

    from services.carrito.readiness import precios_catalogo_para_reserva

    items = [SimpleNamespace(equipo_id=EQ_INEXISTENTE)]
    with pytest.raises(HTTPException) as exc:
        precios_catalogo_para_reserva(conn, items)
    assert exc.value.status_code == 404
