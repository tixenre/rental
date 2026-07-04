"""`facturas.domicilio` (#migración d4e6f8a2b1c3) contra Postgres REAL.

Cubre lo que los tests puros (mockeados) no pueden: que la columna nueva
existe de verdad tras `init_db()`, que `insert_factura`/`get_by_id` la
persisten y la leen sin truncar, y que `emitir_nota_credito` la hereda de la
original en una fila real (sin re-verificar contra el padrón).

OPT-IN y SEGURO POR DEFECTO (mismo gating que los demás `*_db.py`): se saltea
salvo `RESERVAS_DB_TEST=1` + `DATABASE_URL` a una base con 'test' en el nombre.
Trabaja sobre ids altos (>= 9_300_900) y limpia al terminar.

    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rambla_rental_test \
      RESERVAS_DB_TEST=1 SECRET_KEY=dev \
      python -m pytest tests/test_facturacion_domicilio_db.py -v -m integration
"""
import os
from datetime import date
from decimal import Decimal
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
        not (_OPT_IN and _looks_like_test_db()),
        reason="opt-in: setear RESERVAS_DB_TEST=1 + DATABASE_URL a una base de prueba",
    ),
]

_PED = 9_300_900


def _limpiar(conn):
    conn.execute("DELETE FROM facturas WHERE pedido_id = %s", (_PED,))
    conn.execute("DELETE FROM alquileres WHERE id = %s", (_PED,))


@pytest.fixture
def setup():
    from database import get_db, init_db

    init_db()
    conn = get_db()
    try:
        _limpiar(conn)
        conn.execute(
            """INSERT INTO alquileres (id, cliente_nombre, estado, fecha_desde, fecha_hasta,
                                        monto_total, monto_pagado)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (_PED, "Cliente RI SA", "confirmado", "2026-07-01T08:00:00",
             "2026-07-02T20:00:00", 1211, 0),
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


def test_domicilio_persiste_exacto_sin_truncar(setup):
    """`insert_factura(domicilio=...)` → `get_by_id` devuelve el mismo string,
    confirmando que la columna existe (migración aplicada) y no trunca."""
    from database import get_db
    from services.facturacion.repo import get_by_id, insert_factura

    conn = get_db()
    try:
        factura_id = insert_factura(
            conn=conn,
            pedido_id=_PED,
            emisor="pablo",
            ambiente="homologacion",
            cbte_tipo=1,
            pto_vta=3,
            doc_tipo=80,
            doc_nro="20300000003",
            condicion_iva_receptor=1,
            concepto=2,
            imp_neto=Decimal("1001.00"),
            imp_iva=Decimal("210.21"),
            imp_total=Decimal("1211.21"),
            cliente_cuit="20300000003",
            razon_social="Cliente RI SA",
            domicilio="Av. Siempre Viva 742, CABA",
        )
        conn.commit()

        factura = get_by_id(factura_id, conn)
        assert factura.domicilio == "Av. Siempre Viva 742, CABA"
        assert factura.imp_iva == Decimal("210.21")
    finally:
        conn.close()


def test_domicilio_null_cae_a_fallback_en_facturas_viejas(setup):
    """Una factura sin `domicilio` (NULL — emitida antes de esta columna)
    lee `None`, no explota — `pdf.py` cae al valor en vivo del pedido."""
    from database import get_db
    from services.facturacion.repo import get_by_id, insert_factura

    conn = get_db()
    try:
        factura_id = insert_factura(
            conn=conn,
            pedido_id=_PED,
            emisor="pablo",
            ambiente="homologacion",
            cbte_tipo=1,
            pto_vta=3,
            doc_tipo=80,
            doc_nro="20300000003",
            condicion_iva_receptor=1,
            concepto=2,
            imp_neto=Decimal("1001.00"),
            imp_iva=Decimal("210.21"),
            imp_total=Decimal("1211.21"),
            cliente_cuit="20300000003",
            razon_social="Cliente RI SA",
        )
        conn.commit()

        factura = get_by_id(factura_id, conn)
        assert factura.domicilio is None
    finally:
        conn.close()


def test_emitir_nota_credito_hereda_domicilio_en_fila_real(setup, monkeypatch):
    """`emitir_nota_credito` contra Postgres real: la NC insertada tiene el
    MISMO `domicilio` que la factura original, sin re-verificar AFIP."""
    from database import get_db
    from services.facturacion import engine
    from services.facturacion.config import CredARCA
    from services.facturacion.repo import get_by_id, insert_factura, update_cae

    conn = get_db()
    try:
        factura_id = insert_factura(
            conn=conn,
            pedido_id=_PED,
            emisor="pablo",
            ambiente="homologacion",
            cbte_tipo=1,
            pto_vta=3,
            doc_tipo=80,
            doc_nro="20300000003",
            condicion_iva_receptor=1,
            concepto=2,
            imp_neto=Decimal("1001.00"),
            imp_iva=Decimal("210.21"),
            imp_total=Decimal("1211.21"),
            cliente_cuit="20300000003",
            razon_social="Cliente RI SA",
            domicilio="Av. Siempre Viva 742, CABA",
        )
        update_cae(
            factura_id, conn,
            cbte_nro=7, cae="86261839900099", cae_vto=date(2030, 1, 1),
            qr_payload="https://www.afip.gob.ar/fe/qr/?p=abc", raw_response={},
        )
        conn.commit()
    finally:
        conn.close()

    class _FakeWsfe:
        def __init__(self, **kw):
            pass

        def ultimo_autorizado(self, pto_vta, cbte_tipo):
            return 6

        def consultar(self, pto_vta, cbte_tipo, numero):
            return None

        def solicitar_cae(self, comprobante, numero):
            from arca_fe import CaeResult
            return CaeResult(
                resultado="A", cae="86261839900100", cae_vto=date(2030, 1, 1),
                numero=numero,
            )

    def _fake_cred(nombre, conn):
        return CredARCA(
            emisor_id=1, emisor="pablo", condicion_iva="responsable_inscripto",
            ambiente="homologacion", cuit=20111111112, punto_venta=3,
            cert_pem=b"x", key_pem=b"x",
            endpoint_wsaa="https://wsaahomo.afip.gov.ar/ws/services/LoginCms",
            endpoint_wsfe="https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL",
        )

    monkeypatch.setattr(engine, "credenciales", _fake_cred)
    monkeypatch.setattr(engine, "get_ta", lambda emisor, conn: ("tok", "sign"))
    monkeypatch.setattr(engine, "WsfeClient", lambda **kw: _FakeWsfe())

    nc = engine.emitir_nota_credito(factura_id)

    assert nc.domicilio == "Av. Siempre Viva 742, CABA"

    conn = get_db()
    try:
        original = get_by_id(factura_id, conn)
        assert original.estado == "anulada"
    finally:
        conn.close()
