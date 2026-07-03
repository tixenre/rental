"""Fase C-2 (#1219) end-to-end contra Postgres REAL: override manual en $ fijo
(en vez de %), mismo campo de la UI con un selector de tipo al lado.

Recorre:
  1. `_apply_pedido_datos` con `descuento_manual_tipo="monto"` persiste el
     override y recalcula `monto_total` usando el $ fijo (gana OUTRIGHT sobre
     jornadas/cliente, igual que el override en %).
  2. El override en $ se capea al `bruto` — no puede dejar el neto negativo.
  3. Confirmado con override en $: congelado igual que el de %
     (`desglose_de_pedido` no debe divergir de `monto_total` ya persistido).
  4. `/api/cotizar` (HTTP real) con `descuento_manual_tipo=monto` en el
     preview — la misma jerarquía que el guardado, para que el builder no
     muestre un total distinto al que se persiste.

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

CLIENTE_ID = 9_340_001
EQ_ID = 9_340_201
FD, FH = "2031-06-01T10:00:00", "2031-06-04T10:00:00"  # 3 jornadas


@pytest.fixture(autouse=True)
def _sessions_active(monkeypatch):
    monkeypatch.setattr("auth.sessions_store.is_active", lambda jti: {"jti": jti})


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
            (CLIENTE_ID, "Cliente monto fijo", "montofijo-db@test.com", 10),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo) "
            "VALUES (%s,'Equipo monto fijo',5,1000,1)",
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


def test_override_monto_fijo_gana_outright_y_se_persiste(setup):
    from database import get_db
    from routes.alquileres import create_pedido, PedidoCreate, PedidoItem, PedidoDatos, _apply_pedido_datos

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
    assert row["monto_total"] == 2700  # bruto 3000, 10% del cliente (sin override)

    # Override manual de $500 fijos — gana OUTRIGHT sobre el 10% del cliente
    # (que en $ serían 300) aunque el numérico del % sea más chico.
    with get_db() as conn:
        _apply_pedido_datos(
            conn, pid,
            PedidoDatos(descuento_manual_tipo="monto", descuento_manual_monto=500),
            es_admin=True,
        )
        conn.commit()

    with get_db() as conn:
        row = conn.execute(
            "SELECT monto_total, descuento_manual_tipo, descuento_manual_monto "
            "FROM alquileres WHERE id=%s", (pid,),
        ).fetchone()
    assert row["monto_total"] == 2500  # 3000 − 500 (NO 2700, que sería el 10%)
    assert row["descuento_manual_tipo"] == "monto"
    assert row["descuento_manual_monto"] == 500


def test_override_monto_fijo_se_capea_al_bruto_neto_no_negativo(setup):
    from database import get_db
    from routes.alquileres import create_pedido, PedidoCreate, PedidoItem, PedidoDatos, _apply_pedido_datos

    created_ids = setup

    pedido = create_pedido(PedidoCreate(
        cliente_id=CLIENTE_ID,
        fecha_desde=FD, fecha_hasta=FH,
        estado="presupuesto",
        items=[PedidoItem(equipo_id=EQ_ID, cantidad=1, precio_jornada=1000)],
    ), es_admin=True)
    pid = pedido["id"]
    created_ids.append(pid)

    # Bruto es 3000; se pide un descuento de $50.000 — un typo, o simplemente
    # "regalar todo el pedido". No puede dejar el neto negativo.
    with get_db() as conn:
        _apply_pedido_datos(
            conn, pid,
            PedidoDatos(descuento_manual_tipo="monto", descuento_manual_monto=50_000),
            es_admin=True,
        )
        conn.commit()

    with get_db() as conn:
        row = conn.execute("SELECT monto_total FROM alquileres WHERE id=%s", (pid,)).fetchone()
    assert row["monto_total"] == 0  # capeado: neto nunca negativo


def test_confirmado_con_override_monto_queda_congelado(setup):
    """Mismo candado que la Fase C-1 (test_descuento_jerarquia_db.py), pero
    para el override en $ fijo: un pedido confirmado con `descuento_manual_tipo
    ='monto'` no se mueve aunque el cliente cambie de descuento después —
    ni la columna persistida ni el desglose de display."""
    from database import get_db, row_to_dict
    from routes.alquileres import create_pedido, PedidoCreate, PedidoItem, PedidoDatos, _apply_pedido_datos
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
        _apply_pedido_datos(
            conn, pid,
            PedidoDatos(descuento_manual_tipo="monto", descuento_manual_monto=800),
            es_admin=True,
        )
        conn.execute("UPDATE alquileres SET estado='confirmado' WHERE id=%s", (pid,))
        conn.commit()

    with get_db() as conn:
        conn.execute("UPDATE clientes SET descuento=%s WHERE id=%s", (90, CLIENTE_ID))
        conn.commit()

    with get_db() as conn:
        row = conn.execute("SELECT monto_total FROM alquileres WHERE id=%s", (pid,)).fetchone()
        ped = row_to_dict(conn.execute("SELECT * FROM alquileres WHERE id=%s", (pid,)).fetchone())
        ped["items"] = [{"equipo_id": EQ_ID, "cantidad": 1, "precio_jornada": 1000, "cobro_modo": "jornada"}]
        desglose_de_pedido(conn, ped)

    assert row["monto_total"] == 2200  # 3000 − 800, sin cambios
    assert ped["monto_neto"] == 2200  # desglose de display tampoco se movió
    assert ped["descuento_efectivo_pct"] == round(800 / 3000 * 100, 2)
    assert ped["descuento_origen"] == "manual"


def test_cotizar_endpoint_preview_con_override_monto(setup):
    """`/api/cotizar` (HTTP real, admin) con un override en $ en el preview —
    misma jerarquía que el guardado, para que el builder no muestre un total
    "en vivo" distinto al que persiste `_apply_pedido_datos`."""
    import main
    from fastapi.testclient import TestClient
    from auth.session import signer

    created_ids = setup

    # ADMIN_EMAILS en tests = "admin@test.com" (default de conftest.py).
    cookie = f"session={signer.dumps({'email': 'admin@test.com', 'role': 'admin', 'jti': 'montodb-adm'})}"

    with TestClient(main.app, raise_server_exceptions=True) as client:
        resp = client.post(
            "/api/cotizar",
            json={
                "items": [{"equipo_id": EQ_ID, "cantidad": 1}],
                "fecha_desde": FD,
                "fecha_hasta": FH,
                "cliente_id": CLIENTE_ID,
                "descuento_manual_tipo": "monto",
                "descuento_manual_monto": 600,
            },
            headers={"Cookie": cookie},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["bruto"] == 3000
    assert data["descuento_monto"] == 600
    assert data["neto"] == 2400
    assert data["descuento_origen"] == "manual"

    assert not created_ids  # este test no crea pedidos, nada que limpiar
