"""Fase C-3 (#1219) end-to-end contra Postgres REAL: un combo (`equipos.tipo=
'combo'`) no acumula el descuento GLOBAL de cliente/jornadas/manual encima de
su propio descuento por componente (`kit_componentes.descuento_pct`).

Arma un pedido con 1 equipo simple + 1 combo (2 componentes, 10% de línea
c/u), un cliente con 20% de descuento, y verifica que:
  - el precio del combo YA sale rebajado (`precio_combo`, C3 #635 — otro "C3",
    no confundir con este C-3 de #1219),
  - el descuento GLOBAL del cliente se aplica SOLO al bruto del simple,
  - `/api/cotizar` (HTTP real, admin) y `_apply_pedido_items` (guardado)
    coinciden en el mismo neto.

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

CLIENTE_ID = 9_350_001
EQ_SIMPLE = 9_350_201
EQ_COMBO = 9_350_202
EQ_COMP_A = 9_350_203
EQ_COMP_B = 9_350_204
FD, FH = "2031-07-01T10:00:00", "2031-07-02T10:00:00"  # 1 jornada


@pytest.fixture(autouse=True)
def _sessions_active(monkeypatch):
    monkeypatch.setattr("auth.queries.sessions.is_active", lambda jti: {"jti": jti})


def _limpiar(conn, pedido_ids):
    if pedido_ids:
        ph = ",".join(str(p) for p in pedido_ids)
        conn.execute(f"DELETE FROM alquiler_items WHERE pedido_id IN ({ph})")
        conn.execute(f"DELETE FROM alquileres WHERE id IN ({ph})")
    conn.execute("DELETE FROM kit_componentes WHERE equipo_id = %s" % EQ_COMBO)
    conn.execute(
        f"DELETE FROM equipos WHERE id IN ({EQ_SIMPLE},{EQ_COMBO},{EQ_COMP_A},{EQ_COMP_B})"
    )
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
            (CLIENTE_ID, "Cliente combo", "combo-db@test.com", 20),
        )
        # Simple: 10.000/jornada.
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo, tipo) "
            "VALUES (%s,'Equipo simple combo-test',5,10000,1,'simple')",
            (EQ_SIMPLE,),
        )
        # Componentes del combo: 5.000 c/u, 10% de descuento de línea c/u →
        # precio_combo = (5000*0.9 + 5000*0.9) = 9000.
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo, tipo) "
            "VALUES (%s,'Componente A',5,5000,1,'simple')",
            (EQ_COMP_A,),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo, tipo) "
            "VALUES (%s,'Componente B',5,5000,1,'simple')",
            (EQ_COMP_B,),
        )
        conn.execute(
            "INSERT INTO equipos (id, nombre, cantidad, precio_jornada, visible_catalogo, tipo) "
            "VALUES (%s,'Combo test',5,0,1,'combo')",
            (EQ_COMBO,),
        )
        conn.execute(
            "INSERT INTO kit_componentes (equipo_id, componente_id, cantidad, descuento_pct) "
            "VALUES (%s,%s,1,10), (%s,%s,1,10)",
            (EQ_COMBO, EQ_COMP_A, EQ_COMBO, EQ_COMP_B),
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


def test_apply_pedido_items_no_aplica_descuento_global_al_combo(setup):
    """`_apply_pedido_items` (guardado): el 20% del cliente sale SOLO del
    bruto del simple (10.000); el combo (9.000, ya rebajado por su propio
    descuento de componente) queda intacto."""
    from database import get_db
    from routes.alquileres import create_pedido, PedidoCreate, PedidoItem, _apply_pedido_items

    created_ids = setup

    pedido = create_pedido(PedidoCreate(
        cliente_id=CLIENTE_ID,
        fecha_desde=FD, fecha_hasta=FH,
        estado="solicitado",
        items=[PedidoItem(equipo_id=EQ_SIMPLE, cantidad=1, precio_jornada=10000)],
    ), es_admin=True)
    pid = pedido["id"]
    created_ids.append(pid)

    with get_db() as conn:
        p = _apply_pedido_items(conn, pid, [
            PedidoItem(equipo_id=EQ_SIMPLE, cantidad=1, precio_jornada=10000),
            PedidoItem(equipo_id=EQ_COMBO, cantidad=1, precio_jornada=9000),
        ])
        conn.commit()

    # bruto = 10.000 (simple) + 9.000 (combo, ya rebajado) = 19.000.
    # Descuento del cliente (20%) SOLO sobre el simple: 2.000.
    # neto = 19.000 − 2.000 = 17.000 (NO 15.200, que sería 20% de los 19.000).
    assert p["monto_total"] == 17000

    with get_db() as conn:
        row = conn.execute("SELECT monto_total FROM alquileres WHERE id=%s", (pid,)).fetchone()
    assert row["monto_total"] == 17000


def test_cotizar_endpoint_no_aplica_descuento_global_al_combo(setup):
    """`/api/cotizar` (HTTP real, admin) — mismo resultado que el guardado,
    para que el preview del builder no diverja."""
    import main
    from fastapi.testclient import TestClient
    from auth.session import signer

    created_ids = setup

    cookie = f"session={signer.dumps({'email': 'admin@test.com', 'role': 'admin', 'jti': 'combodb-adm'})}"

    with TestClient(main.app, raise_server_exceptions=True) as client:
        resp = client.post(
            "/api/cotizar",
            json={
                "items": [
                    {"equipo_id": EQ_SIMPLE, "cantidad": 1},
                    {"equipo_id": EQ_COMBO, "cantidad": 1},
                ],
                "fecha_desde": FD,
                "fecha_hasta": FH,
                "cliente_id": CLIENTE_ID,
            },
            headers={"Cookie": cookie},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["bruto"] == 19000
    # bruto_descontable excluye el combo (#1219): tope real de un override
    # manual en $ — el front lo usa como `max` del input.
    assert data["bruto_descontable"] == 10000
    assert data["descuento_monto"] == 2000  # 20% de 10.000 (solo el simple)
    assert data["neto"] == 17000

    # Detalle por línea: el combo no lleva descuento propio en el desglose
    # (su `neto` de línea == su `bruto` de línea).
    linea_combo = next(l for l in data["lineas"] if l["equipo_id"] == EQ_COMBO)
    assert linea_combo["bruto"] == linea_combo["neto"] == 9000
    linea_simple = next(l for l in data["lineas"] if l["equipo_id"] == EQ_SIMPLE)
    assert linea_simple["bruto"] == 10000
    assert linea_simple["neto"] == 8000  # 10.000 − 20%

    assert not created_ids  # este test no crea pedidos, nada que limpiar


def test_desglose_de_pedido_no_aplica_descuento_global_al_combo(setup):
    """El desglose de DISPLAY (mail/PDF/portal) también respeta la exención
    del combo — `desglose_de_pedido` deriva `es_combo` de `equipo_tipo`
    (JOIN con `equipos`), no de un flag reimplementado."""
    from database import get_db
    from routes.alquileres import create_pedido, PedidoCreate, PedidoItem, _apply_pedido_items
    from services.finanzas_flujo.pedido import desglose_de_pedido

    created_ids = setup

    pedido = create_pedido(PedidoCreate(
        cliente_id=CLIENTE_ID,
        fecha_desde=FD, fecha_hasta=FH,
        estado="solicitado",
        items=[PedidoItem(equipo_id=EQ_SIMPLE, cantidad=1, precio_jornada=10000)],
    ), es_admin=True)
    pid = pedido["id"]
    created_ids.append(pid)

    with get_db() as conn:
        _apply_pedido_items(conn, pid, [
            PedidoItem(equipo_id=EQ_SIMPLE, cantidad=1, precio_jornada=10000),
            PedidoItem(equipo_id=EQ_COMBO, cantidad=1, precio_jornada=9000),
        ])
        conn.commit()

    with get_db() as conn:
        from routes.alquileres.core import _get_alquiler_detail
        ped = _get_alquiler_detail(conn, pid)
        # `_get_alquiler_detail` ya enriquece con el desglose; verificamos
        # el mismo resultado llamando `desglose_de_pedido` de nuevo (idempotente).
        desglose_de_pedido(conn, ped)

    assert ped["bruto"] == 19000
    assert ped["descuento_monto"] == 2000
    assert ped["monto_neto"] == 17000
