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
    row = conn.execute("SELECT id FROM cuentas WHERE nombre = %s", (nombre,)).fetchone()
    return row[0] if row else None


def _pedido_y_pago(conn, monto, destinatario, fecha="2026-06-15T10:00:00",
                   fecha_desde="2026-06-05T08:00:00", ped=PED):
    conn.execute(
        """INSERT INTO alquileres (id, cliente_nombre, estado, fecha_desde, fecha_hasta,
                                   monto_total, monto_pagado)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
           VALUES (?,?,?,?,?,?,?)""",
        (ped, "Cliente contab", "finalizado", fecha_desde,
         "2026-06-06T20:00:00", monto, monto),
    )
    conn.execute(
        """INSERT INTO alquiler_pagos (pedido_id, monto, concepto, destinatario, metodo, fecha)
           VALUES (%s,%s,%s,%s,%s,%s)""",
           VALUES (?,?,?,?,?,?)""",
        (ped, monto, "pago", destinatario, "transferencia", fecha),
    )


def _mov(conn, tipo, monto, origen=None, destino=None):
    conn.execute(
        """INSERT INTO movimientos (tipo, monto, cuenta_origen_id, cuenta_destino_id, created_by)
           VALUES (%s,%s,%s,%s,%s)""",
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


def test_cobro_de_rambla_alimenta_el_fondo_rambla(conn):
    # Rambla también cobra (default): su plata cae en la caja Fondo Rambla.
    base = _saldo(conn, "Fondo Rambla")
    _pedido_y_pago(conn, 80000, "Rambla")
    assert _saldo(conn, "Fondo Rambla") - base == 80000


def test_ingresos_derivados_agrupan_por_destinatario(conn):
    from contabilidad.saldos import ingresos_derivados

    base = ingresos_derivados(conn).get("Tincho", 0)
    _pedido_y_pago(conn, 150000, "Tincho")
    assert ingresos_derivados(conn).get("Tincho", 0) - base == 150000


def test_alquiler_previo_al_clean_start_no_entra_a_finanzas(conn):
    # Clean start por FECHA DEL ALQUILER (no de pago): un pedido cuyo alquiler fue
    # antes de junio, aunque se cobre en junio, NO suma al saldo de la caja del socio
    # ni a los cobros mensuales. Queda "cobrado y listo" en el pedido, fuera de Finanzas.
    from contabilidad.saldos import ingresos_derivados
    from contabilidad.movimientos import cobros_mensuales

    base_caja = _saldo(conn, "Caja Tincho")
    base_ing = ingresos_derivados(conn).get("Tincho", 0)
    base_cobros = sum(r["monto"] for r in cobros_mensuales(conn, cobrador="Tincho"))

    _pedido_y_pago(conn, 300000, "Tincho",
                   fecha="2026-06-15T10:00:00", fecha_desde="2026-05-20T08:00:00",
                   ped=9_400_050)

    assert _saldo(conn, "Caja Tincho") == base_caja  # la caja no se mueve
    assert ingresos_derivados(conn).get("Tincho", 0) == base_ing  # no deriva ingreso
    assert sum(r["monto"] for r in cobros_mensuales(conn, cobrador="Tincho")) == base_cobros


def test_nombre_se_libera_al_dar_de_baja(conn):
    # El nombre es único solo entre activas: dar de baja una cuenta libera su
    # nombre, así se puede reusar (caso real: renombrar a un nombre que tenía una
    # cuenta vieja de baja).
    from contabilidad.cuentas import crear_cuenta, desactivar_cuenta

    nombre = "Reuso Test 9400"
    c1 = crear_cuenta(conn, nombre=nombre, tipo="caja", por="test")
    desactivar_cuenta(conn, c1["id"], por="test")  # saldo 0 → baja OK
    c2 = crear_cuenta(conn, nombre=nombre, tipo="caja", por="test")
    assert c2["id"] != c1["id"]
    assert c2["nombre"] == nombre


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
    from contabilidad.cuentas import COBRADORES
    from routes.alquileres import DESTINATARIOS_PAGO

    assert set(COBRADORES) == set(DESTINATARIOS_PAGO)


def test_desactivar_falla_si_la_cuenta_tiene_saldo(conn):
    from contabilidad.cuentas import crear_cuenta, desactivar_cuenta

    c = crear_cuenta(conn, nombre="Caja Test ZZ", tipo="caja", saldo_inicial=50000)
    with pytest.raises(ValueError):
        desactivar_cuenta(conn, c["id"])


def _categoria_id(conn, nombre="Otros"):
    row = conn.execute("SELECT id FROM gasto_categorias WHERE nombre = %s", (nombre,)).fetchone()
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


def test_reporte_mensual_cargo_a_socio_no_toca_ganancia(conn):
    # Núcleo del reporte: un CARGO a un socio (Rambla le compró algo) es una
    # transferencia, NO un gasto → aparece en socios_mes pero NO baja la ganancia.
    from contabilidad.movimientos import crear_movimiento
    from contabilidad.reporte_mensual import reporte_mensual

    mes = "2026-06"
    base = reporte_mensual(conn, mes)
    cargo_base = base["socios_mes"]["cargos"]["Pablo"]
    gan_base = base["ganancia_neta"]

    crear_movimiento(
        conn, tipo="transferencia", monto=50000,
        cuenta_origen_id=_cuenta_id(conn, "Efectivo"),
        cuenta_destino_id=_cuenta_id(conn, "Caja Pablo"),
        fecha="2026-06-15", por="test",
    )
    rep = reporte_mensual(conn, mes)
    assert rep["socios_mes"]["cargos"]["Pablo"] - cargo_base == 50000  # aparece como cargo
    assert rep["ganancia_neta"] == gan_base  # NO toca la ganancia


def test_reporte_mensual_gasto_si_baja_ganancia(conn):
    # Contraste: un gasto real SÍ baja la ganancia neta.
    from contabilidad.movimientos import crear_movimiento
    from contabilidad.reporte_mensual import reporte_mensual

    mes = "2026-06"
    gan_base = reporte_mensual(conn, mes)["ganancia_neta"]
    crear_movimiento(
        conn, tipo="gasto", monto=20000, cuenta_origen_id=_cuenta_id(conn, "Efectivo"),
        categoria_id=_categoria_id(conn), fecha="2026-06-10", por="test",
    )
    assert reporte_mensual(conn, mes)["ganancia_neta"] == gan_base - 20000


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


def test_rendicion_cierra_en_cero_y_saldar(conn):
    # El invariante de oro: la rendición está atada al universo del reporte, así
    # que lo cobrado == el total del reporte. Y registrar los sugeridos deja todo
    # saldado. Mes futuro aislado para no chocar con datos de otros tests.
    from contabilidad.rendicion import rendicion, saldar

    MES = "2026-09"
    EQ, PED2 = 9_400_900, 9_400_901
    conn.execute(
        "INSERT INTO equipos (id, nombre, cantidad, dueno) VALUES (%s,%s,%s,%s)",
        (EQ, "Equipo Rend", 3, "Pablo"),
    )
    conn.execute(
        """INSERT INTO alquileres (id, cliente_nombre, estado, fecha_desde, fecha_hasta,
                                   monto_total, monto_pagado)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
           VALUES (?,?,?,?,?,?,?)""",
        (PED2, "Cli rend", "finalizado", "2026-09-05T08:00:00", "2026-09-06T20:00:00",
         100000, 100000),
    )
    conn.execute(
        "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, subtotal) VALUES (%s,%s,%s,%s)",
        (PED2, EQ, 1, 100000),
    )
    conn.execute(
        """INSERT INTO alquiler_pagos (pedido_id, monto, concepto, destinatario, metodo, fecha)
           VALUES (%s,%s,%s,%s,%s,%s)""",
           VALUES (?,?,?,?,?,?)""",
        (PED2, 100000, "pago", "Tincho", "transferencia", "2026-09-15T10:00:00"),
    )

    r = rendicion(conn, MES)
    assert r["total_cobrado"] == r["total_reporte"] == 100000, r
    assert r["cuadra"] is True
    by = {p["persona"]: p for p in r["personas"]}
    assert by["Pablo"]["le_corresponde"] == 50000  # equipo de Pablo → 50/45/5
    assert by["Rambla"]["le_corresponde"] == 45000
    assert by["Tincho"]["le_corresponde"] == 5000
    assert by["Tincho"]["cobro"] == 100000  # todo lo cobró Tincho
    assert sum(p["pendiente"] for p in r["personas"]) == 0  # cierra en cero

    # Registrar los sugeridos deja todo saldado.
    for s in r["sugeridos"]:
        saldar(conn, MES, de=s["de"], a=s["a"], monto=s["monto"], por="test")
    r2 = rendicion(conn, MES)
    assert r2["sugeridos"] == []
    assert all(p["pendiente"] == 0 for p in r2["personas"])


def test_cierre_traba_la_edicion_del_mes(conn):
    from contabilidad.cierres import cerrar_mes, mes_cerrado, reabrir_mes
    from contabilidad.movimientos import crear_movimiento

    MES = "2026-08"
    reabrir_mes(conn, MES)  # idempotente: limpia un cierre colgado de una corrida previa
    assert mes_cerrado(conn, MES) is False
    try:
        cerrar_mes(conn, MES, "test")
        assert mes_cerrado(conn, MES) is True
        # Un gasto fechado en el mes cerrado queda trabado.
        with pytest.raises(ValueError):
            crear_movimiento(
                conn, tipo="gasto", monto=1000, cuenta_origen_id=_cuenta_id(conn, "Efectivo"),
                categoria_id=_categoria_id(conn), fecha="2026-08-10", por="test",
            )
    finally:
        reabrir_mes(conn, MES)
    assert mes_cerrado(conn, MES) is False
    # Reabierto, el mismo gasto entra.
    m = crear_movimiento(
        conn, tipo="gasto", monto=1000, cuenta_origen_id=_cuenta_id(conn, "Efectivo"),
        categoria_id=_categoria_id(conn), fecha="2026-08-10", por="test",
    )
    assert m["id"]


def test_reconciliar_corre(conn):
    from contabilidad.reconciliacion import reconciliar

    r = reconciliar(conn)
    assert "ok" in r
    assert "saldos_negativos" in r and "pagos_sin_socio" in r


def test_beneficiario_se_guarda_y_autocompleta(conn):
    from contabilidad.movimientos import beneficiarios_usados, crear_movimiento, listar_movimientos

    crear_movimiento(
        conn, tipo="gasto", monto=125000, cuenta_origen_id=_cuenta_id(conn, "Efectivo"),
        categoria_id=_categoria_id(conn), beneficiario="Jimena", por="test",
    )
    assert "Jimena" in beneficiarios_usados(conn)
    # filtrable para ver el historial de esa persona
    movs = listar_movimientos(conn, beneficiario="Jimena")
    assert movs and all(m["beneficiario"] == "Jimena" for m in movs)


def test_cobros_mensuales_agrega_por_mes(conn):
    from contabilidad.movimientos import cobros_mensuales

    _pedido_y_pago(conn, 120000, "Tincho", fecha="2026-06-15T10:00:00")
    junio = [r for r in cobros_mensuales(conn, cobrador="Tincho") if r["mes"] == "2026-06"]
    assert junio and junio[0]["monto"] >= 120000  # agrega el cobro del mes


def test_caja_usd_existe_y_totales_por_moneda(conn):
    from contabilidad.saldos import saldos

    s = saldos(conn)
    by = {c["nombre"]: c for c in s["cuentas"]}
    assert by["Dólares"]["moneda"] == "USD"  # caja en dólares seedeada
    assert "USD" in s["totales"] and "ARS" in s["totales"]


def test_transferencia_entre_monedas_distintas_falla(conn):
    from contabilidad.movimientos import crear_movimiento

    with pytest.raises(ValueError):
        crear_movimiento(
            conn, tipo="transferencia", monto=1000,
            cuenta_origen_id=_cuenta_id(conn, "Efectivo"),   # ARS
            cuenta_destino_id=_cuenta_id(conn, "Dólares"),   # USD
            por="test",
        )


def test_crear_y_desactivar_cuenta_vacia(conn):
    from contabilidad.cuentas import crear_cuenta, desactivar_cuenta

    c = crear_cuenta(conn, nombre="Caja Test Vacia ZZ", tipo="caja")
    desactivado = desactivar_cuenta(conn, c["id"])
    assert desactivado["activa"] is False
