"""Fase C-1 (#1219) end-to-end contra Postgres REAL: jerarquía manual > cliente
en vivo > jornadas, y la congelación de precio en pedidos confirmados.

Recorre el flujo completo:
  1. Pedido nuevo sin override → sigue al cliente en vivo (10%).
  2. Cambia el descuento del cliente → el presupuesto se recotiza solo.
  3. Se le pone un override manual (5%) → gana OUTRIGHT (no compite con
     jornadas ni con el cliente).
  4. El cliente cambia de nuevo → el override NO se toca (candado del bug de
     clobbering).
  5. Se confirma el pedido → el descuento del cliente sigue cambiando después,
     pero el pedido confirmado queda CONGELADO (ni `monto_total` ni el
     desglose de display se mueven) — la garantía que el snapshot
     `descuento_cliente_pct` existe para sostener.

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás *_db.py): se saltea
salvo RESERVAS_DB_TEST=1 + DATABASE_URL con 'test' en el nombre.
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

CLIENTE_ID = 9_330_001
EQ_ID = 9_330_201
FD, FH = "2031-05-01T10:00:00", "2031-05-04T10:00:00"  # 3 jornadas


def _limpiar(conn, pedido_ids):
    if pedido_ids:
        ph = ",".join(str(p) for p in pedido_ids)
        conn.execute(f"DELETE FROM alquiler_items WHERE pedido_id IN ({ph})")
        conn.execute(f"DELETE FROM alquileres WHERE id IN ({ph})")
    conn.execute("DELETE FROM equipos WHERE id = %s" % EQ_ID)
    conn.execute("DELETE FROM clientes WHERE id = %s" % CLIENTE_ID)


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    created_ids = []
    try:
        _limpiar(conn, [])
        conn.execute(
            "INSERT INTO clientes (id, nombre, email, descuento) VALUES (%s,%s,%s,%s)",
            (CLIENTE_ID, "Cliente jerarquía", "jerarquia-db@test.com", 10),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo) "
            "VALUES (%s,'Equipo jerarquía',5,1000,1)",
            (EQ_ID,),
        )
        conn.commit()
    finally:
        conn.close()
    yield created_ids
    conn = get_db()
    try:
        _limpiar(conn, created_ids)
        conn.commit()
    finally:
        conn.close()


def test_jerarquia_completa_y_congelamiento_al_confirmar(setup):
    from database import get_db
    from routes.alquileres import (
        create_pedido, PedidoCreate, PedidoItem, PedidoDatos,
        _apply_pedido_datos, propagar_descuento_a_presupuestos,
    )
    from services.finanzas_flujo.pedido import desglose_de_pedido

    created_ids = setup

    # 1. Pedido nuevo, sin override manual → sigue al cliente en vivo (10%).
    pedido = create_pedido(PedidoCreate(
        cliente_id=CLIENTE_ID,
        fecha_desde=FD, fecha_hasta=FH,
        estado="presupuesto",
        items=[PedidoItem(equipo_id=EQ_ID, cantidad=1, precio_jornada=1000)],
    ), es_admin=True)
    pid = pedido["id"]
    created_ids.append(pid)

    with get_db() as conn:
        row = conn.execute("SELECT monto_total, descuento_pct, descuento_cliente_pct "
                            "FROM alquileres WHERE id=%s", (pid,)).fetchone()
    # bruto 3000, 10% del cliente (sin escala de jornadas seedeada = 0%) → 2700.
    assert row["monto_total"] == 2700
    assert (row["descuento_pct"] or 0) == 0  # sin override
    assert float(row["descuento_cliente_pct"]) == 10.0  # snapshot correcto

    # 2. El cliente sube a 20% → el presupuesto se recotiza solo.
    with get_db() as conn:
        conn.execute("UPDATE clientes SET descuento=%s WHERE id=%s", (20, CLIENTE_ID))
        n = propagar_descuento_a_presupuestos(conn, CLIENTE_ID)
        conn.commit()
    assert n == 1
    with get_db() as conn:
        row = conn.execute("SELECT monto_total FROM alquileres WHERE id=%s", (pid,)).fetchone()
    assert row["monto_total"] == 2400  # 3000 − 20%

    # 3. Override manual del 5% — gana OUTRIGHT (menor que el 20% del cliente).
    with get_db() as conn:
        _apply_pedido_datos(conn, pid, PedidoDatos(descuento_pct=5), es_admin=True)
        conn.commit()
    with get_db() as conn:
        row = conn.execute("SELECT monto_total, descuento_pct FROM alquileres WHERE id=%s", (pid,)).fetchone()
    assert row["monto_total"] == 2850  # 3000 − 5% (NO 2400, que sería 20%)
    assert float(row["descuento_pct"]) == 5.0

    # 4. El cliente sube a 50% — el override manual NO se toca (candado del
    #    bug de clobbering: propagar excluye los presupuestos con override).
    with get_db() as conn:
        conn.execute("UPDATE clientes SET descuento=%s WHERE id=%s", (50, CLIENTE_ID))
        n = propagar_descuento_a_presupuestos(conn, CLIENTE_ID)
        conn.commit()
    assert n == 0  # el único presupuesto del cliente TIENE override → no cuenta
    with get_db() as conn:
        row = conn.execute("SELECT monto_total FROM alquileres WHERE id=%s", (pid,)).fetchone()
    assert row["monto_total"] == 2850  # sigue en 5%, no en 50%

    # 5. Se confirma el pedido. El cliente sigue cambiando de descuento
    #    después — el pedido confirmado queda CONGELADO (monto_total Y el
    #    desglose de display, no solo la columna cruda).
    with get_db() as conn:
        conn.execute("UPDATE alquileres SET estado='confirmado' WHERE id=%s", (pid,))
        conn.commit()

    with get_db() as conn:
        conn.execute("UPDATE clientes SET descuento=%s WHERE id=%s", (99, CLIENTE_ID))
        conn.commit()

    with get_db() as conn:
        row = conn.execute("SELECT * FROM alquileres WHERE id=%s", (pid,)).fetchone()
        from database import row_to_dict
        ped = row_to_dict(row)
        ped["items"] = [{"equipo_id": EQ_ID, "cantidad": 1, "precio_jornada": 1000, "cobro_modo": "jornada"}]
        desglose_de_pedido(conn, ped)

    assert ped["monto_total"] == 2850  # la columna persistida no se movió
    assert ped["monto_neto"] == 2850  # y el desglose de DISPLAY tampoco —
    # si desglose_de_pedido hiciera un lookup en vivo de clientes.descuento acá
    # (en vez de leer el snapshot descuento_cliente_pct), este assert fallaría
    # con 2850 vs. lo que fuera un 99%/manual-todavía-gana — la clase de bug
    # "dos cálculos del mismo número" (#405) que este test cierra.
    assert ped["descuento_efectivo_pct"] == 5.0
    assert ped["descuento_origen"] == "manual"


def test_confirmado_sin_override_congela_el_fallback_del_cliente(setup):
    """Caso más estricto que el anterior: un pedido confirmado que NUNCA tuvo
    override manual (depende 100% del fallback al cliente) tiene que quedar
    IGUAL de congelado. Si `desglose_de_pedido` hiciera un lookup en vivo acá
    en vez de leer el snapshot `descuento_cliente_pct`, este test SÍ lo cazaría
    (a diferencia del anterior, donde el override manual enmascara el bug
    porque gana outright sin mirar al cliente)."""
    from database import get_db, row_to_dict
    from routes.alquileres import create_pedido, PedidoCreate, PedidoItem
    from services.finanzas_flujo.pedido import desglose_de_pedido

    created_ids = setup

    pedido = create_pedido(PedidoCreate(
        cliente_id=CLIENTE_ID,
        fecha_desde=FD, fecha_hasta=FH,
        estado="presupuesto",
        items=[PedidoItem(equipo_id=EQ_ID, cantidad=1, precio_jornada=1000)],
    ), es_admin=True)
    pid = pedido["id"]
    created_ids.append(pid)

    with get_db() as conn:
        row = conn.execute("SELECT monto_total FROM alquileres WHERE id=%s", (pid,)).fetchone()
    assert row["monto_total"] == 2700  # 3000 − 10% (el descuento del cliente al crear)

    with get_db() as conn:
        conn.execute("UPDATE alquileres SET estado='confirmado' WHERE id=%s", (pid,))
        conn.commit()

    # El cliente cambia su descuento DESPUÉS de confirmar — no debería mover
    # nada de este pedido.
    with get_db() as conn:
        conn.execute("UPDATE clientes SET descuento=%s WHERE id=%s", (80, CLIENTE_ID))
        conn.commit()

    with get_db() as conn:
        row = conn.execute("SELECT monto_total FROM alquileres WHERE id=%s", (pid,)).fetchone()
        ped = row_to_dict(conn.execute("SELECT * FROM alquileres WHERE id=%s", (pid,)).fetchone())
        ped["items"] = [{"equipo_id": EQ_ID, "cantidad": 1, "precio_jornada": 1000, "cobro_modo": "jornada"}]
        desglose_de_pedido(conn, ped)

    assert row["monto_total"] == 2700  # columna persistida, sin cambios
    assert ped["monto_neto"] == 2700  # desglose de DISPLAY — el que este test protege
    assert ped["descuento_efectivo_pct"] == 10.0  # el 10% congelado, NO el 80% actual
    assert ped["descuento_origen"] == "cliente"
