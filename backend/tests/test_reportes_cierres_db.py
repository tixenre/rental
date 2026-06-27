"""Cierres de liquidación (#721) contra Postgres REAL.

Ejerce lo que los tests puros no cubren: que cerrar un mes CONGELA la foto (cambiar
el modelo o editar un pedido después no altera el mes cerrado), que el reporte sirve
la foto en vez de recalcular, que reabrir vuelve a vivo, y que la reconciliación caza
un pedido editado dentro de un mes cerrado.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás `*_db.py`): se saltea salvo
`RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre. Trabaja
sobre ids altos (>= 9_400_000) y limpia al terminar.

    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rambla_rental_test \
      RESERVAS_DB_TEST=1 SECRET_KEY=dev \
      python -m pytest tests/test_reportes_cierres_db.py -v -m integration
"""
import json
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

E_PABLO, E_RAMBLA = 9_400_001, 9_400_002
P_JUNIO, P_EDIT = 9_400_101, 9_400_102
ALL_EQ = (E_PABLO, E_RAMBLA)
ALL_PED = (P_JUNIO, P_EDIT)
MES = "2026-06"


def _limpiar(conn):
    conn.execute("DELETE FROM liquidacion_cierres WHERE mes IN ('2026-06','2026-07')")
    conn.execute("DELETE FROM alquiler_pagos WHERE pedido_id IN %s" % (ALL_PED,))
    conn.execute("DELETE FROM alquiler_items WHERE pedido_id IN %s" % (ALL_PED,))
    conn.execute("DELETE FROM alquileres WHERE id IN %s" % (ALL_PED,))
    conn.execute("DELETE FROM equipos WHERE id IN %s" % (ALL_EQ,))


def _modelo(conn, modelo: dict):
    conn.execute(
        """INSERT INTO app_settings (key, value, updated_by)
           VALUES ('comisiones_modelo', %s, 'test')
           ON CONFLICT (key) DO UPDATE SET value = excluded.value""",
           ON CONFLICT (key) DO UPDATE SET value = excluded.value""",
        (json.dumps(modelo),),
    )


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, dueno) VALUES (%s,%s,%s,%s)",
            (E_PABLO, "Equipo Pablo", 5, "Pablo"),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, dueno) VALUES (%s,%s,%s,%s)",
            (E_RAMBLA, "Equipo Rambla", 5, "Rambla"),
        )
        # P_JUNIO: 100k de Pablo, alquiler y saldo en junio → cuenta para junio
        # (fecha_desde dentro del clean start, ver liquidacion.LIQUIDACION_INICIO).
        conn.execute(
            """INSERT INTO alquileres (id, cliente_nombre, estado, fecha_desde, monto_total, monto_pagado)
               VALUES (%s,%s,%s,%s,%s,%s)""",
               VALUES (?,?,?,?,?,?)""",
            (P_JUNIO, "Cliente", "finalizado", "2026-06-05T08:00:00", 100000, 100000),
        )
        conn.execute(
            "INSERT INTO alquiler_items (pedido_id, equipo_id, cantidad, subtotal) VALUES (%s,%s,%s,%s)",
            (P_JUNIO, E_PABLO, 1, 100000),
        )
        conn.execute(
            "INSERT INTO alquiler_pagos (pedido_id, monto, concepto, fecha) VALUES (%s,%s,%s,%s)",
            (P_JUNIO, 100000, "pago", "2026-06-15T10:00:00"),
        )
        # Modelo default conocido.
        _modelo(conn, {"Pablo": {"Pablo": 50, "Rambla": 45, "Tincho": 5}, "Rambla": {"Rambla": 100}})
        conn.commit()
    finally:
        conn.close()

    yield

    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute("DELETE FROM app_settings WHERE key = 'comisiones_modelo'")
        conn.commit()
    finally:
        conn.close()


def _conn():
    from database import get_db

    return get_db()


def test_cerrar_congela_frente_a_cambio_de_modelo(setup):
    from reportes.cierres import cerrar_mes
    from reportes.liquidacion import liquidar

    conn = _conn()
    try:
        # En vivo, junio reparte Pablo 50/45/5 sobre 100k.
        vivo = liquidar(conn, "2026-06-01", "2026-06-30")
        assert vivo["resumen"]["por_beneficiario"]["Pablo"] == 50000

        # Cerramos junio → foto inmutable.
        snap = cerrar_mes(conn, MES, "tincho@test")
        assert snap["cerrado"] is True
        assert snap["cerrado_por"] == "tincho@test"
        assert snap["resumen"]["por_beneficiario"]["Pablo"] == 50000

        # Cambiamos el modelo: ahora Pablo se lleva todo.
        _modelo(conn, {"Pablo": {"Pablo": 100}, "Rambla": {"Rambla": 100}})
        conn.commit()

        # El mes ABIERTO recalcularía (Pablo 100k); el CERRADO sigue 50k.
        from reportes.cierres import snapshot_de

        frozen = snapshot_de(conn, MES)
        assert frozen["resumen"]["por_beneficiario"]["Pablo"] == 50000, "la foto debe quedar firme"
        # Y un mes distinto (julio, abierto) usa el modelo nuevo.
        julio_vivo = liquidar(conn, "2026-07-01", "2026-07-31")
        assert julio_vivo["resumen"]["total"] == 0  # no hay pedidos en julio
    finally:
        conn.close()


def test_reabrir_vuelve_a_vivo(setup):
    from reportes.cierres import cerrar_mes, cierre_de, reabrir_mes, snapshot_de

    conn = _conn()
    try:
        cerrar_mes(conn, MES, "x")
        assert cierre_de(conn, MES) is not None
        assert reabrir_mes(conn, MES) is True
        assert cierre_de(conn, MES) is None
        assert snapshot_de(conn, MES) is None
        # Reabrir un mes ya abierto devuelve False (no había nada que borrar).
        assert reabrir_mes(conn, MES) is False
    finally:
        conn.close()


def test_reconciliacion_caza_pedido_editado_en_mes_cerrado(setup):
    from reportes.cierres import cerrar_mes
    from reportes.reconciliacion import reconciliar

    conn = _conn()
    try:
        cerrar_mes(conn, MES, "x")
        # Reconciliación limpia recién cerrado.
        rec = reconciliar(conn)
        assert rec["mes_cerrado_desactualizado"]["cantidad"] == 0, rec["mes_cerrado_desactualizado"]

        # Editamos el pedido saldado en junio DESPUÉS del cierre (bump updated_at).
        conn.execute(
            "UPDATE alquileres SET updated_at = CURRENT_TIMESTAMP + INTERVAL '1 hour' WHERE id = %s",
            (P_JUNIO,),
        )
        conn.commit()

        rec2 = reconciliar(conn)
        stale = rec2["mes_cerrado_desactualizado"]
        assert P_JUNIO in stale["ids"], stale
        assert MES in stale["meses"], stale
        assert rec2["ok"] is False
    finally:
        conn.close()
