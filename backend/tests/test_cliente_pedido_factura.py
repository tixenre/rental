"""Tests de GET /api/cliente/pedidos/{id}/factura — la factura como documento
más del portal cliente (a diferencia de remito/contrato/albarán, depende de si
la factura ya fue EMITIDA, no del estado del pedido).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from routes.cliente_portal import documentos as documentos_routes
from services.facturacion.repo import Factura, pedidos_con_factura_emitida

pytestmark = pytest.mark.unit


def _fake_request():
    return SimpleNamespace(state=SimpleNamespace(session=None))


def _fake_factura() -> Factura:
    return Factura(
        id=14, pedido_id=422, emisor="santini", ambiente="produccion",
        cbte_tipo=11, pto_vta=2, cbte_nro=1, cae="86261839900000", cae_vto=None,
        doc_tipo=96, doc_nro="42289220", condicion_iva_receptor=5,
        concepto=2, imp_neto=5700, imp_iva=0, imp_total=5700, moneda="PES",
        cliente_cuit=None, razon_social=None, qr_payload=None, pdf_key=None,
        estado="emitida", nota_credito_de=None, raw_request=None,
        raw_response=None, errores=None, fecha_emision=None,
        created_at=None, created_by=None,
    )


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, pedido_row):
        self._pedido_row = pedido_row

    def execute(self, sql, params=None):
        return _FakeCursor(self._pedido_row)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def test_factura_404_si_el_pedido_no_es_del_cliente(monkeypatch):
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.require_cliente",
        lambda request: {"cliente_id": 1},
    )
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.get_db", lambda: _FakeConn(pedido_row=None)
    )

    with pytest.raises(HTTPException) as ei:
        asyncio.run(documentos_routes.cliente_pedido_factura(422, _fake_request()))
    assert ei.value.status_code == 404


def test_factura_404_si_todavia_no_se_emitio(monkeypatch):
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.require_cliente",
        lambda request: {"cliente_id": 1},
    )
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.get_db",
        lambda: _FakeConn(pedido_row={"id": 422}),
    )
    monkeypatch.setattr(
        "services.facturacion.repo.get_factura_principal_emitida",
        lambda pedido_id, conn: None,
    )

    with pytest.raises(HTTPException) as ei:
        asyncio.run(documentos_routes.cliente_pedido_factura(422, _fake_request()))
    assert ei.value.status_code == 404


def test_factura_503_si_faltan_datos_de_arca(monkeypatch):
    """factura_html falla fuerte si faltan datos de ARCA — el route lo
    convierte en 503, nunca en un 500 crudo."""
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.require_cliente",
        lambda request: {"cliente_id": 1},
    )
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.get_db",
        lambda: _FakeConn(pedido_row={"id": 422}),
    )
    monkeypatch.setattr(
        "services.facturacion.repo.get_factura_principal_emitida",
        lambda pedido_id, conn: _fake_factura(),
    )
    monkeypatch.setattr(
        "services.facturacion.engine._get_pedido", lambda conn, pedido_id: {"id": pedido_id}
    )

    def _raise(*a, **kw):
        raise ValueError("ComprobanteFiscal incompleto, faltan: cae")

    monkeypatch.setattr("services.facturacion.comprobante_render.factura_html", _raise)

    with pytest.raises(HTTPException) as ei:
        asyncio.run(documentos_routes.cliente_pedido_factura(422, _fake_request()))
    assert ei.value.status_code == 503


def test_factura_format_html_devuelve_preview(monkeypatch):
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.require_cliente",
        lambda request: {"cliente_id": 1},
    )
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.get_db",
        lambda: _FakeConn(pedido_row={"id": 422}),
    )
    monkeypatch.setattr(
        "services.facturacion.repo.get_factura_principal_emitida",
        lambda pedido_id, conn: _fake_factura(),
    )
    monkeypatch.setattr(
        "services.facturacion.engine._get_pedido", lambda conn, pedido_id: {"id": pedido_id}
    )
    monkeypatch.setattr(
        "services.facturacion.comprobante_render.factura_html",
        lambda factura, pedido, **_: "<html>FACTURA-CLIENTE</html>",
    )

    resp = asyncio.run(
        documentos_routes.cliente_pedido_factura(422, _fake_request(), format="html")
    )
    assert resp.status_code == 200
    assert b"FACTURA-CLIENTE" in resp.body


def test_factura_format_pdf_default_devuelve_inline(monkeypatch):
    """El portal cliente sirve `inline` (preview embebido), no `attachment`
    como el admin — mismo criterio que remito/contrato/albarán."""
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.require_cliente",
        lambda request: {"cliente_id": 1},
    )
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.get_db",
        lambda: _FakeConn(pedido_row={"id": 422}),
    )
    monkeypatch.setattr(
        "services.facturacion.repo.get_factura_principal_emitida",
        lambda pedido_id, conn: _fake_factura(),
    )
    monkeypatch.setattr(
        "services.facturacion.engine._get_pedido", lambda conn, pedido_id: {"id": pedido_id}
    )
    monkeypatch.setattr(
        "services.facturacion.comprobante_render.factura_html", lambda factura, pedido, **_: "<html></html>"
    )
    monkeypatch.setattr(
        "services.facturacion.signing_cert.get_or_create_signing_cert",
        lambda conn: (b"cert", b"key"),
    )
    monkeypatch.setattr(
        "arca_fe.asegurar_pdf", lambda pdf_bytes, cert_pem, key_pem: pdf_bytes
    )

    async def _fake_render_pdf(html, **_):
        return b"%PDF-FAKE%"

    monkeypatch.setattr("routes.cliente_portal.documentos._render_pdf", _fake_render_pdf)

    resp = asyncio.run(documentos_routes.cliente_pedido_factura(422, _fake_request()))
    assert resp.status_code == 200
    assert resp.body == b"%PDF-FAKE%"
    assert "inline" in resp.headers["content-disposition"]
    assert "Factura-C-00002-00000001.pdf" in resp.headers["content-disposition"]


def test_factura_pdf_queda_firmada_igual_que_en_el_admin(monkeypatch):
    """Regresión: a diferencia del canal admin (`descargar_pdf_factura`), el PDF de factura del
    portal cliente no quedaba firmado/protegido — misma factura, mismo `asegurar_pdf`."""
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.require_cliente",
        lambda request: {"cliente_id": 1},
    )
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.get_db",
        lambda: _FakeConn(pedido_row={"id": 422}),
    )
    monkeypatch.setattr(
        "services.facturacion.repo.get_factura_principal_emitida",
        lambda pedido_id, conn: _fake_factura(),
    )
    monkeypatch.setattr(
        "services.facturacion.engine._get_pedido", lambda conn, pedido_id: {"id": pedido_id}
    )
    monkeypatch.setattr(
        "services.facturacion.comprobante_render.factura_html", lambda factura, pedido, **_: "<html></html>"
    )
    monkeypatch.setattr(
        "services.facturacion.signing_cert.get_or_create_signing_cert",
        lambda conn: (b"cert", b"key"),
    )

    firmado_con = {}

    def _fake_asegurar_pdf(pdf_bytes, cert_pem, key_pem):
        firmado_con["cert_pem"] = cert_pem
        firmado_con["key_pem"] = key_pem
        return b"%PDF-FIRMADO%"

    monkeypatch.setattr("arca_fe.asegurar_pdf", _fake_asegurar_pdf)

    async def _fake_render_pdf(html, **_):
        return b"%PDF-SIN-FIRMAR%"

    monkeypatch.setattr("routes.cliente_portal.documentos._render_pdf", _fake_render_pdf)

    resp = asyncio.run(documentos_routes.cliente_pedido_factura(422, _fake_request()))
    assert resp.body == b"%PDF-FIRMADO%"
    assert firmado_con == {"cert_pem": b"cert", "key_pem": b"key"}


def test_factura_format_html_no_pide_certificado(monkeypatch):
    """El preview HTML no necesita firmar nada — `get_or_create_signing_cert` ni se llama."""
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.require_cliente",
        lambda request: {"cliente_id": 1},
    )
    monkeypatch.setattr(
        "routes.cliente_portal.documentos.get_db",
        lambda: _FakeConn(pedido_row={"id": 422}),
    )
    monkeypatch.setattr(
        "services.facturacion.repo.get_factura_principal_emitida",
        lambda pedido_id, conn: _fake_factura(),
    )
    monkeypatch.setattr(
        "services.facturacion.engine._get_pedido", lambda conn, pedido_id: {"id": pedido_id}
    )
    monkeypatch.setattr(
        "services.facturacion.comprobante_render.factura_html",
        lambda factura, pedido, **_: "<html>PREVIEW</html>",
    )

    def _boom(conn):
        raise AssertionError("no debería pedir el certificado para un preview HTML")

    monkeypatch.setattr("services.facturacion.signing_cert.get_or_create_signing_cert", _boom)

    resp = asyncio.run(
        documentos_routes.cliente_pedido_factura(422, _fake_request(), format="html")
    )
    assert resp.status_code == 200


# ── pedidos_con_factura_emitida (batch, para el listado) ────────────────────


def test_pedidos_con_factura_emitida_batch():
    rows = [{"pedido_id": 422}, {"pedido_id": 100}]

    class _Cur:
        def fetchall(self_inner):
            return rows

    class _Conn:
        def execute(self_inner, sql, params=None):
            return _Cur()

    result = pedidos_con_factura_emitida([422, 100, 999], _Conn())
    assert result == {422, 100}


def test_pedidos_con_factura_emitida_lista_vacia_no_pega_a_la_db():
    class _Conn:
        def execute(self_inner, sql, params=None):
            raise AssertionError("no debería consultar la DB con lista vacía")

    assert pedidos_con_factura_emitida([], _Conn()) == set()
