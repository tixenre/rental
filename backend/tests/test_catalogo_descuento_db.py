"""`proyectar_lista`/`proyectar_uno` con descuento de catálogo — Postgres REAL.

El caso end-to-end que el test puro (`test_catalogo_descuento.py`) no cubre:
fechas reales → `jornadas_periodo` → `obtener_descuento_jornadas` (Decimal de
Postgres) + `obtener_descuento_cliente`, aplicado a una lista real con un
combo mezclado (Fase C-3, #1219: el combo queda afuera).

OPT-IN y SEGURO POR DEFECTO. Ids/jornadas altos (9_620_7xx) + limpieza
antes/después (`descuentos_jornada`/`clientes` commitean de verdad, no hay
rollback transaccional posible entre fixtures que abren su propia conexión).
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
        not _OPT_IN, reason="opt-in: setear RESERVAS_DB_TEST=1 + DATABASE_URL a una base de prueba"
    ),
    pytest.mark.skipif(
        _OPT_IN and not _looks_like_test_db(),
        reason=f"DATABASE_URL ({_DB_NAME!r}) no parece base de test — abortado por seguridad",
    ),
]

CLIENTE_ID = 9_620_701
EQ_SIMPLE = 9_620_702
EQ_COMBO = 9_620_703
EQ_COMP = 9_620_704
# Puntos ancla de la escala — jornadas altas para no chocar con una escala real
# configurada (mismo criterio que test_descuentos_jornada_db.py).
J_BAJO, J_ALTO = 9_620, 9_630
# 5 jornadas exactas: DESDE 00:00 → HASTA +5*24h.
DESDE, HASTA = "2031-09-01", "2031-09-06"


def _limpiar(conn):
    conn.execute("DELETE FROM kit_componentes WHERE equipo_id = %s", (EQ_COMBO,))
    conn.execute("DELETE FROM equipos WHERE id IN (%s,%s,%s)", (EQ_SIMPLE, EQ_COMBO, EQ_COMP))
    conn.execute("DELETE FROM clientes WHERE id = %s", (CLIENTE_ID,))
    conn.execute("DELETE FROM descuentos_jornada WHERE jornadas IN (%s,%s)", (J_BAJO, J_ALTO))


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, visible_catalogo, tipo, precio_jornada) "
            "VALUES (%s,%s,5,1,'simple',10000)",
            (EQ_SIMPLE, "eq-simple-descuento-test"),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, visible_catalogo, tipo, precio_jornada) "
            "VALUES (%s,%s,5,1,'simple',6000)",
            (EQ_COMP, "eq-componente-descuento-test"),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, visible_catalogo, tipo, precio_jornada) "
            "VALUES (%s,%s,5,1,'combo',0)",
            (EQ_COMBO, "eq-combo-descuento-test"),
        )
        conn.execute(
            "INSERT INTO kit_componentes (equipo_id, componente_id, cantidad, descuento_pct) "
            "VALUES (%s,%s,1,0)",
            (EQ_COMBO, EQ_COMP),
        )
        # Escala: 5 jornadas (J_BAJO) → 10%; se queda en 10% para cualquier
        # jornadas >= J_BAJO hasta J_ALTO (interpolar_descuento_jornadas se
        # queda en el último punto para jornadas >= el ancla mayor — acá
        # jornadas=5 es MENOR a J_BAJO=9620, así que cae al primer punto: 10%).
        conn.execute(
            "INSERT INTO descuentos_jornada (jornadas, pct) VALUES (%s,%s),(%s,%s)",
            (J_BAJO, 10.0, J_ALTO, 40.0),
        )
        conn.execute(
            "INSERT INTO clientes (id, nombre, email, descuento) VALUES (%s,%s,%s,%s)",
            (CLIENTE_ID, "Cliente descuento catálogo", "descuento-catalogo-db@test.com", 25),
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


def test_proyectar_lista_sin_cliente_aplica_solo_jornadas(setup):
    from database import get_db
    from services.catalogo.proyeccion import proyectar_lista

    with get_db() as conn:
        resultado = proyectar_lista(
            conn,
            filtro_sql="FROM equipos e WHERE e.id = ANY(%s)",
            filtro_params=[[EQ_SIMPLE, EQ_COMBO]],
            desde=DESDE, hasta=HASTA, cliente_id=None,
        )
    por_id = {e["id"]: e for e in resultado["items"]}

    simple = por_id[EQ_SIMPLE]
    assert simple["descuento_pct"] == 10.0
    assert simple["descuento_origen"] == "jornadas"
    assert simple["precio_jornada_final"] == 9000  # 10000 * 0.9

    # El combo NO acumula el descuento global (Fase C-3, #1219): precio intacto.
    combo = por_id[EQ_COMBO]
    assert combo["descuento_pct"] == 0.0
    assert combo["descuento_origen"] is None
    assert combo["precio_jornada_final"] == combo["precio_jornada"] == 6000


def test_proyectar_lista_cliente_con_descuento_mayor_gana(setup):
    from database import get_db
    from services.catalogo.proyeccion import proyectar_lista

    with get_db() as conn:
        resultado = proyectar_lista(
            conn,
            filtro_sql="FROM equipos e WHERE e.id = ANY(%s)",
            filtro_params=[[EQ_SIMPLE]],
            desde=DESDE, hasta=HASTA, cliente_id=CLIENTE_ID,
        )
    simple = resultado["items"][0]
    # Cliente 25% > jornadas 10% → gana el cliente.
    assert simple["descuento_pct"] == 25.0
    assert simple["descuento_origen"] == "cliente"
    assert simple["precio_jornada_final"] == 7500


def test_proyectar_lista_sin_fechas_no_calcula_descuento(setup):
    from database import get_db
    from services.catalogo.proyeccion import proyectar_lista

    with get_db() as conn:
        resultado = proyectar_lista(
            conn,
            filtro_sql="FROM equipos e WHERE e.id = ANY(%s)",
            filtro_params=[[EQ_SIMPLE]],
            cliente_id=CLIENTE_ID,  # sin desde/hasta: no hay jornadas, no se calcula nada
        )
    simple = resultado["items"][0]
    assert "descuento_pct" not in simple


def test_proyectar_uno_mismo_criterio_que_la_lista(setup):
    from database import get_db
    from services.catalogo.proyeccion import proyectar_uno

    with get_db() as conn:
        equipo = proyectar_uno(conn, EQ_SIMPLE, desde=DESDE, hasta=HASTA, cliente_id=CLIENTE_ID)
    assert equipo["descuento_pct"] == 25.0
    assert equipo["descuento_origen"] == "cliente"
    assert equipo["precio_jornada_final"] == 7500
