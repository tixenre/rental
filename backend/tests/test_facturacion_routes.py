"""Tests HTTP/contrato de routes/facturacion.py — transporte fino.

La lógica de negocio vive en services/facturacion/engine.py (testeada en
test_facturacion_engine.py); acá se clava el contrato del handler: guard de
admin a nivel HTTP (rutea + gatea, sin DB — mismo patrón que
test_clientes_merge_route.py), mapeo de errores (ValueError→400,
RuntimeError→503), y los branches format=html/pdf del PDF on-demand.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main
from routes import facturacion as facturacion_routes
from services.facturacion.repo import Factura

pytestmark = pytest.mark.unit

_http = TestClient(main.app, raise_server_exceptions=False)


def _fake_request():
    return SimpleNamespace(state=SimpleNamespace(session=None))


def _fake_factura(estado="emitida") -> Factura:
    return Factura(
        id=1, pedido_id=422, emisor="santini", ambiente="homologacion",
        cbte_tipo=11, pto_vta=2, cbte_nro=1, cae="86261839900000", cae_vto=None,
        doc_tipo=96, doc_nro="42289220", condicion_iva_receptor=5,
        concepto=2, imp_neto=5700, imp_iva=0, imp_total=5700, moneda="PES",
        cliente_cuit=None, razon_social=None, qr_payload=None, pdf_key=None,
        estado=estado, nota_credito_de=None, raw_request=None,
        raw_response=None, errores=None, fecha_emision=None,
        created_at=None, created_by=None,
    )


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class _FakeRow(dict):
    """Simula una fila de psycopg (acceso por índice de columna)."""


class _FakeConnConEmail:
    """Como `_FakeConn` pero con `execute` para el SELECT de email del cliente
    (regresión: `enviar_mail_factura` consultaba `c.owner_email`, columna que no
    existe en `clientes` — rompía con UndefinedColumn siempre. Ver `c.email`)."""

    def __init__(self, row=None):
        self._row = row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def execute(self, _sql, _params=None):
        row = self._row

        class _R:
            def fetchone(self_inner):
                return row

        return _R()


# ── Guard de admin a nivel HTTP (rutea + gatea, sin DB) ─────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/facturas/1/pdf"),
        ("POST", "/api/facturas/1/enviar-mail"),
        ("POST", "/api/facturas/1/nota-credito"),
        ("POST", "/api/alquileres/1/facturar"),
        ("GET", "/api/alquileres/1/facturas"),
        ("GET", "/api/admin/facturas"),
        ("GET", "/api/admin/facturacion/estado"),
        ("GET", "/api/admin/emisores-arca"),
        ("POST", "/api/admin/emisores-arca"),
        ("PUT", "/api/admin/emisores-arca/1"),
        ("DELETE", "/api/admin/emisores-arca/1"),
        ("POST", "/api/admin/emisores-arca/1/cert"),
    ],
)
def test_rutas_facturacion_gatean_por_admin(method, path):
    r = _http.request(method, path)
    assert r.status_code != 422, f"{method} {path} no rutea bien (revisar orden de paths)"
    assert r.status_code in (401, 403)


# ── facturar_pedido / nota_credito: mapeo de errores del engine ─────────────


def test_facturar_pedido_value_error_es_400(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr(
        "services.facturacion.engine.emitir_factura",
        lambda pedido_id, emitido_por=None: (_ for _ in ()).throw(ValueError("no confirmado")),
    )
    with pytest.raises(HTTPException) as ei:
        facturacion_routes.facturar_pedido(1, _fake_request())
    assert ei.value.status_code == 400


def test_facturar_pedido_runtime_error_es_503_nunca_500(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr(
        "services.facturacion.engine.emitir_factura",
        lambda pedido_id, emitido_por=None: (_ for _ in ()).throw(RuntimeError("ARCA caída")),
    )
    with pytest.raises(HTTPException) as ei:
        facturacion_routes.facturar_pedido(1, _fake_request())
    assert ei.value.status_code == 503


def test_nota_credito_value_error_es_400(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr(
        "services.facturacion.engine.emitir_nota_credito",
        lambda factura_id, emitido_por=None: (_ for _ in ()).throw(ValueError("ya anulada")),
    )
    with pytest.raises(HTTPException) as ei:
        facturacion_routes.nota_credito(1, _fake_request())
    assert ei.value.status_code == 400


def test_nota_credito_runtime_error_es_503(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr(
        "services.facturacion.engine.emitir_nota_credito",
        lambda factura_id, emitido_por=None: (_ for _ in ()).throw(RuntimeError("timeout WSFE")),
    )
    with pytest.raises(HTTPException) as ei:
        facturacion_routes.nota_credito(1, _fake_request())
    assert ei.value.status_code == 503


# ── descargar_pdf_factura: 404 / 400 / format=html / format=pdf ────────────


def test_descargar_pdf_404_si_no_existe(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr("services.facturacion.repo.get_by_id", lambda factura_id, conn: None)

    with pytest.raises(HTTPException) as ei:
        asyncio.run(facturacion_routes.descargar_pdf_factura(999, _fake_request()))
    assert ei.value.status_code == 404


def test_descargar_pdf_400_si_no_emitida(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.repo.get_by_id", lambda factura_id, conn: _fake_factura("pendiente")
    )

    with pytest.raises(HTTPException) as ei:
        asyncio.run(facturacion_routes.descargar_pdf_factura(1, _fake_request()))
    assert ei.value.status_code == 400


def test_descargar_pdf_format_html_devuelve_preview_sin_renderer(monkeypatch):
    """`format=html` no debe pasar por Playwright — devuelve el HTML tal cual."""
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.repo.get_by_id", lambda factura_id, conn: _fake_factura()
    )
    monkeypatch.setattr(
        "services.facturacion.engine._get_pedido", lambda conn, pedido_id: {"id": pedido_id}
    )
    monkeypatch.setattr(
        "services.facturacion.pdf.factura_html", lambda factura, pedido, **_: "<html>FACTURA-X</html>"
    )

    resp = asyncio.run(
        facturacion_routes.descargar_pdf_factura(1, _fake_request(), format="html")
    )
    assert resp.status_code == 200
    assert b"FACTURA-X" in resp.body


def test_descargar_pdf_format_pdf_default_es_attachment(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.repo.get_by_id", lambda factura_id, conn: _fake_factura()
    )
    monkeypatch.setattr(
        "services.facturacion.engine._get_pedido", lambda conn, pedido_id: {"id": pedido_id}
    )
    monkeypatch.setattr(
        "services.facturacion.pdf.factura_html", lambda factura, pedido, **_: "<html></html>"
    )

    async def _fake_render_pdf(html, **_):
        return b"%PDF-FAKE%"

    monkeypatch.setattr("pdf._render_pdf", _fake_render_pdf)

    resp = asyncio.run(facturacion_routes.descargar_pdf_factura(1, _fake_request()))
    assert resp.status_code == 200
    assert resp.body == b"%PDF-FAKE%"
    assert "attachment" in resp.headers["content-disposition"]
    assert "Factura-C-00002-00000001.pdf" in resp.headers["content-disposition"]


# ── enviar_mail_factura: la columna real es c.email, no c.owner_email ───────


def test_enviar_mail_factura_no_rompe_con_undefined_column(monkeypatch):
    """Regresión: consultaba `c.owner_email` (columna inexistente en `clientes`,
    vive en otra tabla) — rompía SIEMPRE con UndefinedColumn. Ahora usa `c.email`."""
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr(
        "routes.facturacion.get_db",
        lambda: _FakeConnConEmail(_FakeRow(email="cliente@example.com", nombre="Ana", apellido="Gómez")),
    )
    monkeypatch.setattr(
        "services.facturacion.repo.get_by_id", lambda factura_id, conn: _fake_factura()
    )
    monkeypatch.setattr(
        "services.facturacion.engine._get_pedido", lambda conn, pedido_id: {"id": pedido_id}
    )
    monkeypatch.setattr(
        "services.facturacion.pdf.factura_html", lambda factura, pedido, **_: "<html></html>"
    )

    async def _fake_render_pdf(html, **_):
        return b"%PDF-FAKE%"

    monkeypatch.setattr("pdf._render_pdf", _fake_render_pdf)

    sent = {}

    def _fake_send_raw_email(**kwargs):
        sent.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr("services.email.send_raw_email", _fake_send_raw_email)

    resp = asyncio.run(facturacion_routes.enviar_mail_factura(1, _fake_request()))
    assert resp == {"ok": True, "to": "cliente@example.com"}
    assert sent.get("to") == "cliente@example.com"


def test_enviar_mail_factura_400_si_sin_email(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr(
        "routes.facturacion.get_db",
        lambda: _FakeConnConEmail(_FakeRow(email=None, nombre="Ana", apellido="Gómez")),
    )
    monkeypatch.setattr(
        "services.facturacion.repo.get_by_id", lambda factura_id, conn: _fake_factura()
    )
    monkeypatch.setattr(
        "services.facturacion.engine._get_pedido", lambda conn, pedido_id: {"id": pedido_id}
    )
    monkeypatch.setattr(
        "services.facturacion.pdf.factura_html", lambda factura, pedido, **_: "<html></html>"
    )

    with pytest.raises(HTTPException) as ei:
        asyncio.run(facturacion_routes.enviar_mail_factura(1, _fake_request()))
    assert ei.value.status_code == 400
