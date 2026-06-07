"""Contabilidad (#809) contra Postgres REAL — lo que el test puro no cubre.

Ejerce el cableado con datos reales: la DERIVACIÓN de ingresos desde
`alquiler_pagos` (un cobro de cliente alimenta la caja de su socio, sin cargar
nada a mano), los movimientos moviendo plata entre cuentas, y la baja lógica.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás `*_db.py`): se saltea
salvo `RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre.
Cada test trabaja en una transacción que se DESCARTA con rollback al terminar
(no toca datos commiteados) y usa ids altos (>= 9_400_000).

    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rambla_rental_test \
      RESERVAS_DB_TEST=1 SECRET_KEY=dev \
      python -m pytest tests/test_contabilidad_db.py -v -m integration
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

PED = 9_400_001


@pytest.fixture
def conn():
    """Conexión transaccional: lo que inserta el test se DESCARTA con rollback al
    terminar, así no quedan datos sucios (no hace falta limpieza manual)."""
    from database import get_db, init_db

    init_db()  # garantiza el esquema + el seed de cuentas (su propia conexión/commit)
    c = get_db()
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def _saldo(conn, nombre: str):
    from contabilidad.saldos import saldos
    for f in saldos(conn)["cuentas"]:
        if f["nombre"] == nombre:
            return f["saldo"]
    return None


def _cuenta_id(conn, nombre: str):
    row = conn.execute("SELECT id FROM cuentas WHERE nombre = ?", (nombre,)).fetchone()
    return row[0] if row else None


def _pedido_y_pago(conn, monto, destinatario, fecha="2026-06-15T10:00:00"):
    conn.execute(
        """INSERT INTO alquileres (id, cliente_nombre, estado, fecha_desde, fecha_hasta,
                                   monto_total, monto_pagado)
           VALUES (?,?,?,?,?,?,?)""",
        (PED, "Cliente contab", "finalizado", "2026-06-05T08:00:00",
         "2026-06-06T20:00:00", monto, monto),
    )
    conn.execute(
        """INSERT INTO alquiler_pagos (pedido_id, monto, concepto, destinatario, metodo, fecha)
           VALUES (?,?,?,?,?,?)""",
        (PED, monto, "pago", destinatario, "transferencia", fecha),
    )


def _mov(conn, tipo, monto, origen=None, destino=None):
    conn.execute(
        """INSERT INTO movimientos (tipo, monto, cuenta_origen_id, cuenta_destino_id, created_by)
           VALUES (?,?,?,?,?)""",
        (tipo, monto, origen, destino, "test"),
    )


def test_cobro_de_cliente_alimenta_la_caja_del_socio(conn):
    # El corazón de Fase 1: sin cargar ningún movimiento, un pago cobrado por
    # Tincho hace subir el saldo de Caja Tincho exactamente por ese monto.
    base = _saldo(conn, "Caja Tincho")
    _pedido_y_pago(conn, 200000, "Tincho")
    despues = _saldo(conn, "Caja Tincho")
    assert despues - base == 200000


def test_el_cobro_no_toca_la_caja_del_otro_socio(conn):
    base_pablo = _saldo(conn, "Caja Pablo")
    _pedido_y_pago(conn, 200000, "Tincho")
    assert _saldo(conn, "Caja Pablo") == base_pablo  # Pablo no se mueve


def test_ingresos_derivados_agrupan_por_destinatario(conn):
    from contabilidad.saldos import ingresos_derivados

    base = ingresos_derivados(conn).get("Tincho", 0)
    _pedido_y_pago(conn, 150000, "Tincho")
    assert ingresos_derivados(conn).get("Tincho", 0) - base == 150000


def test_gasto_baja_el_saldo_de_la_caja_de_origen(conn):
    base = _saldo(conn, "Efectivo")
    _mov(conn, "gasto", 25000, origen=_cuenta_id(conn, "Efectivo"))
    assert _saldo(conn, "Efectivo") - base == -25000


def test_transferencia_mueve_plata_entre_cuentas(conn):
    base_pablo = _saldo(conn, "Caja Pablo")
    base_fondo = _saldo(conn, "Fondo Rambla")
    _mov(conn, "transferencia", 60000,
         origen=_cuenta_id(conn, "Caja Pablo"), destino=_cuenta_id(conn, "Fondo Rambla"))
    assert _saldo(conn, "Caja Pablo") - base_pablo == -60000
    assert _saldo(conn, "Fondo Rambla") - base_fondo == 60000


def test_saldo_iguala_la_derivacion(conn):
    # Invariante: el saldo de una caja de socio (sin movimientos que la toquen)
    # == sus ingresos derivados (+ su saldo inicial, que es 0 en el seed).
    from contabilidad.saldos import ingresos_derivados
    _pedido_y_pago(conn, 90000, "Pablo")
    assert _saldo(conn, "Caja Pablo") == ingresos_derivados(conn).get("Pablo", 0)


def test_socios_coinciden_con_destinatarios_de_pago(conn):
    # Anti-drift: los socios del módulo contable son exactamente los destinatarios
    # posibles de un cobro (si alguien agrega un tercero, este test obliga a tocar
    # los dos lados).
    from contabilidad.cuentas import SOCIOS
    from routes.alquileres import DESTINATARIOS_PAGO

    assert set(SOCIOS) == set(DESTINATARIOS_PAGO)


def test_desactivar_falla_si_la_cuenta_tiene_saldo(conn):
    from contabilidad.cuentas import crear_cuenta, desactivar_cuenta

    c = crear_cuenta(conn, nombre="Caja Test ZZ", tipo="caja", saldo_inicial=50000)
    with pytest.raises(ValueError):
        desactivar_cuenta(conn, c["id"])


def _categoria_id(conn, nombre="Otros"):
    row = conn.execute("SELECT id FROM gasto_categorias WHERE nombre = ?", (nombre,)).fetchone()
    return row[0] if row else None


def test_crear_gasto_baja_caja_y_anular_lo_restaura(conn):
    # El engine (no SQL crudo): un gasto baja la caja; anularlo la restaura, porque
    # los movimientos anulados no cuentan para el saldo.
    from contabilidad.movimientos import anular_movimiento, crear_movimiento

    base = _saldo(conn, "Efectivo")
    mov = crear_movimiento(
        conn, tipo="gasto", monto=12000, cuenta_origen_id=_cuenta_id(conn, "Efectivo"),
        categoria_id=_categoria_id(conn), por="test",
    )
    assert _saldo(conn, "Efectivo") - base == -12000
    anular_movimiento(conn, mov["id"], motivo="cargado por error", por="test")
    assert _saldo(conn, "Efectivo") == base  # restaurado


def test_listar_movimientos_resuelve_nombres(conn):
    from contabilidad.movimientos import crear_movimiento, listar_movimientos

    crear_movimiento(
        conn, tipo="transferencia", monto=5000,
        cuenta_origen_id=_cuenta_id(conn, "Caja Pablo"),
        cuenta_destino_id=_cuenta_id(conn, "Banco"), por="test",
    )
    movs = listar_movimientos(conn, tipo="transferencia")
    assert any(
        m["cuenta_origen_nombre"] == "Caja Pablo" and m["cuenta_destino_nombre"] == "Banco"
        for m in movs
    )


def test_gasto_necesita_categoria(conn):
    from contabilidad.movimientos import crear_movimiento

    with pytest.raises(ValueError):
        crear_movimiento(conn, tipo="gasto", monto=1000,
                         cuenta_origen_id=_cuenta_id(conn, "Efectivo"), por="test")


def test_crear_y_desactivar_cuenta_vacia(conn):
    from contabilidad.cuentas import crear_cuenta, desactivar_cuenta

    c = crear_cuenta(conn, nombre="Caja Test Vacia ZZ", tipo="caja")
    desactivado = desactivar_cuenta(conn, c["id"])
    assert desactivado["activa"] is False
