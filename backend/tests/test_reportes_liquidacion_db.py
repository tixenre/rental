"""Liquidación (#88) contra Postgres REAL — la parte que los tests puros no cubren.

Ejerce el SQL delicado: la window function que decide la fecha de saldado, el
prorrateo del total entre equipos, y el reparto por dueño. Más la reconciliación.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás `*_db.py`): se saltea
salvo `RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre.
Trabaja sobre ids altos (>= 9_300_000) y limpia al terminar.

    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rambla_rental_test \
      RESERVAS_DB_TEST=1 SECRET_KEY=dev \
      python -m pytest tests/test_reportes_liquidacion_db.py -v -m integration
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

# Equipos: Rambla, Pablo, Tincho. Pedidos. Ids altos para no chocar con datos.
E_RAMBLA, E_PABLO, E_TINCHO = 9_300_001, 9_300_002, 9_300_003
P_CRUCE, P_PARCIAL, P_MIXTO, P_LEGACY, P_SOBRE, P_PREJUNIO = (
    9_300_101, 9_300_102, 9_300_103, 9_300_104, 9_300_105, 9_300_106,
)
ALL_EQ = (E_RAMBLA, E_PABLO, E_TINCHO)
ALL_PED = (P_CRUCE, P_PARCIAL, P_MIXTO, P_LEGACY, P_SOBRE, P_PREJUNIO)


def _limpiar(conn):
    conn.execute("DELETE FROM alquiler_pagos WHERE pedido_id IN %s" % (ALL_PED,))
    conn.execute("DELETE FROM alquiler_items WHERE pedido_id IN %s" % (ALL_PED,))
    conn.execute("DELETE FROM alquileres WHERE id IN %s" % (ALL_PED,))
    conn.execute("DELETE FROM equipos WHERE id IN %s" % (ALL_EQ,))


def _equipo(conn, eid, nombre, dueno):
    conn.execute(
        "INSERT INTO equipos (id, nombre, cantidad, dueno) VALUES (%s,%s,%s,%s)",
        (eid, nombre, 5, dueno),
    )


def _pedido(conn, pid, monto_total, items, monto_pagado=0, estado="finalizado",
            fecha_desde="2026-06-05T08:00:00"):
    # fecha_desde default DENTRO del clean start (junio 2026) → cuenta para la
    # liquidación. Los tests que prueban la exclusión pasan una fecha anterior.
    conn.execute(
        """INSERT INTO alquileres (id, cliente_nombre, estado, fecha_desde, fecha_hasta,
                                   monto_total, monto_pagado)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (pid, "Cliente liquidación", estado, fecha_desde, "2026-06-06T20:00:00",
         monto_total, monto_pagado),
    )
    for equipo_id, subtotal in items:
        conn.execute(
            "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, subtotal) VALUES (%s,%s,%s,%s)",
            (pid, equipo_id, 1, subtotal),
        )


def _pago(conn, pid, monto, fecha, concepto="pago"):
    conn.execute(
        "INSERT INTO alquiler_pagos (pedido_id, monto, concepto, fecha) VALUES (%s,%s,%s,%s)",
        (pid, monto, concepto, fecha),
    )


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        _equipo(conn, E_RAMBLA, "Equipo Rambla", "Rambla")
        _equipo(conn, E_PABLO, "Equipo Pablo", "Pablo")
        _equipo(conn, E_TINCHO, "Equipo Tincho", "Tincho")

        # P_CRUCE: total 100k, seña 40k en MAYO + saldo 60k en JUNIO → saldado en junio.
        _pedido(conn, P_CRUCE, 100000, [(E_PABLO, 100000)], monto_pagado=100000)
        _pago(conn, P_CRUCE, 40000, "2026-05-20T10:00:00", "seña")
        _pago(conn, P_CRUCE, 60000, "2026-06-03T10:00:00", "saldo")

        # P_PARCIAL: total 100k, solo 40k pagado → NO saldado → no aparece.
        _pedido(conn, P_PARCIAL, 100000, [(E_RAMBLA, 100000)], monto_pagado=40000)
        _pago(conn, P_PARCIAL, 40000, "2026-06-10T10:00:00", "seña")

        # P_MIXTO: total 100k, 2 equipos (Rambla 60k + Pablo 40k), saldado en junio.
        _pedido(conn, P_MIXTO, 100000, [(E_RAMBLA, 60000), (E_PABLO, 40000)], monto_pagado=100000)
        _pago(conn, P_MIXTO, 100000, "2026-06-15T10:00:00", "pago total")

        # P_LEGACY: marcado pagado por la columna SIN ledger → debe caer en reconciliación.
        _pedido(conn, P_LEGACY, 50000, [(E_RAMBLA, 50000)], monto_pagado=50000)

        # P_SOBRE: cobrado 80k pero el total quedó en 50k (editado a la baja tras cobrar)
        # → sobrepagado, debe caer en reconciliación. Saldado en julio (mes neutral
        # para no contaminar las aserciones de junio).
        _pedido(conn, P_SOBRE, 50000, [(E_RAMBLA, 50000)], monto_pagado=80000)
        _pago(conn, P_SOBRE, 80000, "2026-07-20T10:00:00", "pago")

        # P_PREJUNIO: alquiler de MAYO (antes del clean start), pagado 100% en JUNIO.
        # NO debe contar para la liquidación: el corte es por fecha del alquiler.
        _pedido(conn, P_PREJUNIO, 100000, [(E_RAMBLA, 100000)], monto_pagado=100000,
                fecha_desde="2026-05-15T08:00:00")
        _pago(conn, P_PREJUNIO, 100000, "2026-06-20T10:00:00", "pago")

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


def _liquidar(desde, hasta):
    from database import get_db
    from reportes.liquidacion import liquidar

    conn = get_db()
    try:
        return liquidar(conn, desde, hasta)
    finally:
        conn.close()


def test_cruce_se_atribuye_al_mes_de_saldado(setup):
    # En MAYO (solo la seña entró) el pedido NO debe aparecer: todavía no estaba
    # saldado. El total de mayo no incluye los 100k de P_CRUCE.
    mayo = _liquidar("2026-05-01", "2026-05-31")
    assert mayo["resumen"]["total"] == 0, mayo["resumen"]

    # En JUNIO sí aparece completo (saldó el 3/6), repartido 50/45/5 (es de Pablo).
    junio = _liquidar("2026-06-01", "2026-06-30")
    pb = junio["resumen"]["por_beneficiario"]
    # P_CRUCE (Pablo 100k → 50/45/5) + P_MIXTO (Rambla 60k→100% + Pablo 40k→50/45/5).
    # Pablo: 50000 + 20000 = 70000; Rambla: 45000 + 60000 + 18000 = 123000; Tincho: 5000 + 2000 = 7000.
    assert pb["Pablo"] == 70000, pb
    assert pb["Rambla"] == 123000, pb
    assert pb["Tincho"] == 7000, pb


def test_parcial_no_aparece(setup):
    junio = _liquidar("2026-06-01", "2026-06-30")
    # P_PARCIAL (40k de 100k) no está saldado → no suma. El total de junio son los
    # dos pedidos saldados (100k + 100k = 200k), no incluye el parcial NI el
    # P_PREJUNIO (alquiler de mayo, fuera del clean start) aunque saldó en junio.
    assert junio["resumen"]["total"] == 200000, junio["resumen"]


def test_clean_start_excluye_alquiler_previo_a_junio(setup):
    # P_PREJUNIO: alquiler de mayo, pagado 100% el 20/6. El corte es por fecha del
    # alquiler → NO cuenta para la liquidación de junio, pese a saldar en junio.
    junio = _liquidar("2026-06-01", "2026-06-30")
    pedidos_dia = {d["dia"]: d["total"] for d in junio["por_dia"]}
    # No hay bucket el 20/6 (solo entró P_PREJUNIO ese día, y está excluido).
    assert "2026-06-20" not in pedidos_dia, pedidos_dia
    # Y el total de junio no incluye sus 100k.
    assert junio["resumen"]["total"] == 200000, junio["resumen"]

    # Tampoco aparece reabriendo el rango a todo 2026 (el corte no depende del rango).
    anio = _liquidar("2026-01-01", "2026-12-31")
    # Solo cuentan los saldados DENTRO del clean start: junio (200k) + julio
    # (P_SOBRE 50k de total, saldó 80k pero imputa el total). P_PREJUNIO fuera.
    assert all(m["mes"] >= "2026-06" for m in anio["por_mes"]), anio["por_mes"]


def test_prorrateo_conserva_la_plata(setup):
    junio = _liquidar("2026-06-01", "2026-06-30")
    # La suma del reparto == la suma de lo generado por dueño == total.
    suma_benef = sum(junio["resumen"]["por_beneficiario"].values())
    suma_generado = sum(d["monto_generado"] for d in junio["por_dueno"])
    assert suma_benef == junio["resumen"]["total"]
    assert suma_generado == junio["resumen"]["total"]


def test_buckets_diarios(setup):
    junio = _liquidar("2026-06-01", "2026-06-30")
    dias = {d["dia"]: d["total"] for d in junio["por_dia"]}
    assert dias.get("2026-06-03") == 100000  # P_CRUCE saldó este día
    assert dias.get("2026-06-15") == 100000  # P_MIXTO


def test_veces_alquilado(setup):
    junio = _liquidar("2026-06-01", "2026-06-30")
    # En junio hay 2 pedidos saldados (P_CRUCE + P_MIXTO).
    assert junio["resumen"]["pedidos"] == 2
    duenos = {d["dueno"]: d for d in junio["por_dueno"]}
    # El equipo de Pablo salió en ambos (P_CRUCE y P_MIXTO) → 2 veces.
    pablo = duenos["Pablo"]
    fx = {e["equipo"]: e for e in pablo["equipos"]}["Equipo Pablo"]
    assert fx["veces"] == 2
    assert pablo["pedidos"] == 2


def test_reconciliacion_caza_pagado_sin_ledger(setup):
    from database import get_db
    from reportes.reconciliacion import reconciliar

    conn = get_db()
    try:
        rec = reconciliar(conn)
    finally:
        conn.close()
    # P_LEGACY está marcado pagado por la columna pero sin ledger → debe listarse.
    assert P_LEGACY in rec["pagados_sin_ledger"]["ids"], rec["pagados_sin_ledger"]
    # P_SOBRE se cobró por encima de su total actual → sobrepagado.
    assert P_SOBRE in rec["sobrepagados"]["ids"], rec["sobrepagados"]
    assert rec["ok"] is False
