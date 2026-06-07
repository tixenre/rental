"""Línea personalizada (#805) contra Postgres REAL.

Una línea personalizada (equipo_id NULL) es un ítem de texto libre que NO reserva
stock y NO debe contaminar el motor de reservas. Verifica que:
  - el gate (`validar_stock`) ignora la línea libre (no la cuenta como demanda) y
    sigue contando bien el equipo de catálogo del mismo pedido;
  - la disponibilidad no se ve afectada por líneas libres de otros pedidos;
  - la lectura (`_get_alquiler_items`) devuelve la línea libre con su `nombre`
    tomado de `nombre_libre`, `equipo_id` None y el `cobro_modo`.

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

EQ = 9_300_001
P1, P2 = 9_300_101, 9_300_102
FD, FH = "2026-11-01T08:00:00", "2026-11-02T20:00:00"
ALL_PED = (P1, P2)


def _limpiar(conn):
    conn.execute("DELETE FROM alquiler_items WHERE pedido_id IN (%s,%s)" % ALL_PED)
    conn.execute("DELETE FROM alquileres WHERE id IN (%s,%s)" % ALL_PED)
    conn.execute("DELETE FROM equipos WHERE id = %s" % EQ)


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (?,?,?)", (EQ, "Equipo libre-test", 1))
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


def _crear_pedido(conn, pid, estado):
    conn.execute(
        "INSERT INTO alquileres (id, cliente_nombre, estado, fecha_desde, fecha_hasta) VALUES (?,?,?,?,?)",
        (pid, "Cliente test (#805)", estado, FD, FH),
    )


def test_linea_libre_no_rompe_el_gate_ni_reserva_stock(setup):
    from database import get_db
    from reservas.gate import validar_stock

    conn = get_db()
    try:
        # P1 confirmado: 1 unidad del equipo (stock total = 1) + una línea libre.
        _crear_pedido(conn, P1, "confirmado")
        conn.execute(
            "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad) VALUES (?,?,?)",
            (P1, EQ, 1),
        )
        conn.execute(
            "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, nombre_libre, cobro_modo, precio_jornada) "
            "VALUES (?,?,?,?,?,?)",
            (P1, None, 2, "Flete", "fijo", 20000),
        )
        conn.commit()

        # El gate de P1 no se rompe por la línea libre (equipo_id None) y P1 entra
        # en stock (1 unidad, hay 1).
        assert validar_stock(conn, P1, FD, FH) == []

        # P2 pide el MISMO equipo en el mismo rango → sin stock (la línea libre de
        # P1 no liberó ni ocupó nada; el cuello sigue siendo la 1 unidad del equipo).
        _crear_pedido(conn, P2, "presupuesto")
        conn.execute(
            "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad) VALUES (?,?,?)",
            (P2, EQ, 1),
        )
        conn.execute(
            "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, nombre_libre, cobro_modo) "
            "VALUES (?,?,?,?,?)",
            (P2, None, 1, "Operador", "jornada"),
        )
        conn.commit()
        problemas = validar_stock(conn, P2, FD, FH)
        assert len(problemas) == 1 and "Equipo libre-test" in problemas[0]
    finally:
        conn.rollback()
        conn.close()


def test_lectura_incluye_la_linea_libre(setup):
    from database import get_db
    from routes.alquileres import _get_alquiler_items

    conn = get_db()
    try:
        _crear_pedido(conn, P1, "confirmado")
        conn.execute(
            "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, orden) VALUES (?,?,?,?)",
            (P1, EQ, 1, 0),
        )
        conn.execute(
            "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, nombre_libre, cobro_modo, precio_jornada, orden) "
            "VALUES (?,?,?,?,?,?,?)",
            (P1, None, 1, "Flete", "fijo", 15000, 1),
        )
        conn.commit()

        items = _get_alquiler_items(conn, P1)
        assert len(items) == 2
        libre = [i for i in items if i["equipo_id"] is None]
        assert len(libre) == 1
        assert libre[0]["nombre"] == "Flete"
        assert libre[0]["cobro_modo"] == "fijo"
    finally:
        conn.rollback()
        conn.close()
