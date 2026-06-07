"""Calendario de disponibilidad por equipo (#808) contra Postgres REAL.

Verifica `estado_diario_equipo`: (1) una reserva de un KIT que contiene la hoja
pone la hoja en 'reservado' ese día (la expansión recursiva backward cuenta), y
(2) una reserva directa parcial del stock da 'parcial'. Reusa los mismos primitivos
del motor (no recalcula overlap).

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

HOJA, KIT = 9_500_001, 9_500_002
MULTI = 9_500_003  # equipo con stock 2 para el caso parcial
PK = 9_500_101
# Día de prueba: reserva que cubre TODO el 2026-08-10 (de medianoche a medianoche,
# con margen) → ocupación de día completo, para distinguir 'reservado' de 'parcial'.
FD, FH = "2026-08-09T00:00:00", "2026-08-12T00:00:00"
DESDE, HASTA = "2026-08-10", "2026-08-10"


def _limpiar(conn):
    conn.execute("DELETE FROM alquiler_items WHERE pedido_id = %s" % PK)
    conn.execute("DELETE FROM alquileres WHERE id = %s" % PK)
    conn.execute("DELETE FROM kit_componentes WHERE equipo_id IN (%s,%s,%s)" % (HOJA, KIT, MULTI))
    conn.execute("DELETE FROM equipos WHERE id IN (%s,%s,%s)" % (HOJA, KIT, MULTI))


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (?,?,?)", (HOJA, "Hoja 808", 1))
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (?,?,?)", (KIT, "Kit 808", 9999))
        conn.execute("INSERT INTO equipos (id, nombre, cantidad) VALUES (?,?,?)", (MULTI, "Multi 808", 2))
        conn.execute(
            "INSERT INTO kit_componentes (equipo_id, componente_id, cantidad) VALUES (?,?,?)",
            (KIT, HOJA, 1),
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


def _reservar(conn, equipo_id, cant):
    conn.execute(
        "INSERT INTO alquileres (id, cliente_nombre, estado, fecha_desde, fecha_hasta) VALUES (?,?,?,?,?)",
        (PK, "Cliente 808", "confirmado", FD, FH),
    )
    conn.execute(
        "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad) VALUES (?,?,?)",
        (PK, equipo_id, cant),
    )


def test_reserva_de_kit_pone_la_hoja_reservada(setup):
    from database import get_db
    from reservas.disponibilidad import estado_diario_equipo

    conn = get_db()
    try:
        _reservar(conn, KIT, 1)  # reservar el KIT consume la hoja (stock 1)
        conn.commit()
        res = estado_diario_equipo(conn, HOJA, DESDE, HASTA)
        assert res["stock"] == 1
        assert res["dias"]["2026-08-10"] == "reservado"
    finally:
        conn.rollback()
        conn.close()


def test_reserva_directa_parcial_del_stock(setup):
    from database import get_db
    from reservas.disponibilidad import estado_diario_equipo

    conn = get_db()
    try:
        _reservar(conn, MULTI, 1)  # 1 de 2 unidades reservadas todo el día
        conn.commit()
        res = estado_diario_equipo(conn, MULTI, DESDE, HASTA)
        assert res["stock"] == 2
        assert res["dias"]["2026-08-10"] == "parcial"
    finally:
        conn.rollback()
        conn.close()
