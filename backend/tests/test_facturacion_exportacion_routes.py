"""Tests HTTP/contrato de las rutas de Factura de Exportación (WSFEXv1) en routes/facturacion.py.

Mismo patrón que test_facturacion_routes.py: la lógica de negocio vive en
services/facturacion/engine_exportacion.py (testeada en test_engine_exportacion.py); acá se clava
el contrato del handler — guard de admin, parseo del body (`_comprobante_exportacion_desde_body`),
mapeo de errores (ValueError→400, ArcaError por subtipo, RuntimeError→503)."""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

import main
from routes import facturacion as facturacion_routes
from services.facturacion.repo_exportacion import FacturaExportacion

pytestmark = pytest.mark.unit

_http = TestClient(main.app, raise_server_exceptions=False)


def _fake_request(method="POST") -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": "/x",
        "raw_path": b"/x",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def _valid_body(**overrides) -> dict:
    base = {
        "nombre_emisor": "santini",
        "emisor": {"cuit": "20-30123456-3", "punto_venta": 3, "condicion_iva": "monotributo"},
        "receptor": {"razon_social": "Acme Corp", "pais_destino_id": 203},
        "exportacion": {"incoterm": "FOB", "permiso_embarque": "X123"},
        "concepto": 1,
        "importe_neto": "1000.00",
        "fecha": "2026-07-05",
        "moneda": "USD",
        "cotizacion": "1000",
    }
    base.update(overrides)
    return base


def _fake_factura_exportacion(estado="emitida") -> FacturaExportacion:
    return FacturaExportacion(
        id=1, emisor="santini", ambiente="homologacion", cbte_tipo=19, pto_vta=3,
        cbte_nro=1, cae="70012345670000", cae_vto=None,
        receptor_razon_social="Acme Corp", receptor_pais_destino=203,
        receptor_domicilio=None, receptor_id_impositivo=None,
        incoterm="FOB", permiso_embarque="X123", moneda="USD", cotizacion=1000,
        imp_total=1000, estado=estado, nota_credito_de=None, qr_payload=None,
        raw_request=None, raw_response=None, errores=None,
        fecha_emision=None, created_at=None, created_by=None,
    )


# ── Guard de admin a nivel HTTP ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/api/admin/facturacion/exportacion"),
        ("GET", "/api/admin/facturacion/exportacion"),
        ("POST", "/api/admin/facturacion/exportacion/1/nota-credito"),
        ("GET", "/api/facturas-exportacion/1/pdf"),
    ],
)
def test_rutas_exportacion_gatean_por_admin(method, path):
    r = _http.request(method, path)
    assert r.status_code != 422, f"{method} {path} no rutea bien (revisar orden de paths)"
    assert r.status_code in (401, 403)


# ── crear_factura_exportacion: parseo de body + mapeo de errores ────────────


def test_crear_factura_exportacion_sin_nombre_emisor_es_400(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    with pytest.raises(HTTPException) as ei:
        facturacion_routes.crear_factura_exportacion(
            _fake_request(), _valid_body(nombre_emisor="")
        )
    assert ei.value.status_code == 400


def test_crear_factura_exportacion_body_invalido_es_400(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    with pytest.raises(HTTPException) as ei:
        facturacion_routes.crear_factura_exportacion(
            _fake_request(), _valid_body(moneda="dolares")  # no son 3 caracteres
        )
    assert ei.value.status_code == 400


def test_crear_factura_exportacion_arma_y_delega_al_engine(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    llamadas = []

    def _fake_emitir(nombre_emisor, comprobante, *, emitido_por=None):
        llamadas.append((nombre_emisor, comprobante))
        return _fake_factura_exportacion()

    monkeypatch.setattr(
        "services.facturacion.engine_exportacion.emitir_factura_exportacion", _fake_emitir
    )

    result = facturacion_routes.crear_factura_exportacion(_fake_request(), _valid_body())

    assert len(llamadas) == 1
    assert llamadas[0][0] == "santini"
    assert result["cae"] == "70012345670000"
    assert result["estado"] == "emitida"


def test_crear_factura_exportacion_value_error_es_400(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr(
        "services.facturacion.engine_exportacion.emitir_factura_exportacion",
        lambda nombre_emisor, comprobante, emitido_por=None: (_ for _ in ()).throw(
            ValueError("emisor no habilitado para exportación")
        ),
    )
    with pytest.raises(HTTPException) as ei:
        facturacion_routes.crear_factura_exportacion(_fake_request(), _valid_body())
    assert ei.value.status_code == 400


def test_crear_factura_exportacion_runtime_error_es_503_nunca_500(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr(
        "services.facturacion.engine_exportacion.emitir_factura_exportacion",
        lambda nombre_emisor, comprobante, emitido_por=None: (_ for _ in ()).throw(
            RuntimeError("ARCA caída")
        ),
    )
    with pytest.raises(HTTPException) as ei:
        facturacion_routes.crear_factura_exportacion(_fake_request(), _valid_body())
    assert ei.value.status_code == 503


@pytest.mark.parametrize(
    "excepcion,status_esperado",
    [
        pytest.param("ArcaBusinessError", 422, id="business-422"),
        pytest.param("ArcaResponseError", 502, id="response-502"),
        pytest.param("ArcaAuthError", 503, id="auth-503"),
        pytest.param("ArcaNetworkError", 503, id="network-503"),
    ],
)
def test_crear_factura_exportacion_arca_error_status_por_subtipo(
    monkeypatch, excepcion, status_esperado
):
    import arca_fe.errores as errores_mod

    exc_cls = getattr(errores_mod, excepcion)
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr(
        "services.facturacion.engine_exportacion.emitir_factura_exportacion",
        lambda nombre_emisor, comprobante, emitido_por=None: (_ for _ in ()).throw(
            exc_cls("motivo real de AFIP")
        ),
    )
    with pytest.raises(HTTPException) as ei:
        facturacion_routes.crear_factura_exportacion(_fake_request(), _valid_body())
    assert ei.value.status_code == status_esperado
    assert "motivo real de AFIP" in ei.value.detail


# ── nota_credito_exportacion ─────────────────────────────────────────────────


def test_nota_credito_exportacion_delega_al_engine(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    llamadas = []

    def _fake_nc(factura_id, comprobante_nc, *, emitido_por=None):
        llamadas.append((factura_id, comprobante_nc))
        return _fake_factura_exportacion()

    monkeypatch.setattr(
        "services.facturacion.engine_exportacion.emitir_nota_credito_exportacion", _fake_nc
    )

    body = _valid_body(cbtes_asoc=[{"tipo": 19, "punto_venta": 3, "numero": 1}])
    result = facturacion_routes.nota_credito_exportacion(1, _fake_request(), body)

    assert len(llamadas) == 1
    assert llamadas[0][0] == 1
    assert llamadas[0][1].es_nota_credito is True
    assert result["estado"] == "emitida"


def test_nota_credito_exportacion_value_error_es_400(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr(
        "services.facturacion.engine_exportacion.emitir_nota_credito_exportacion",
        lambda factura_id, comprobante_nc, emitido_por=None: (_ for _ in ()).throw(
            ValueError("solo se puede anular una emitida")
        ),
    )
    body = _valid_body(cbtes_asoc=[{"tipo": 19, "punto_venta": 3, "numero": 1}])
    with pytest.raises(HTTPException) as ei:
        facturacion_routes.nota_credito_exportacion(1, _fake_request(), body)
    assert ei.value.status_code == 400


# ── listar_facturas_exportacion ──────────────────────────────────────────────


def test_listar_facturas_exportacion_devuelve_lista_y_count(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.repo_exportacion.list_facturas_exportacion",
        lambda conn, **kw: [_fake_factura_exportacion(), _fake_factura_exportacion()],
    )

    result = facturacion_routes.listar_facturas_exportacion(_fake_request(method="GET"))
    assert result["count"] == 2
    assert len(result["facturas"]) == 2


# ── descargar_pdf_factura_exportacion: 404 / 400 / format=html / format=pdf ──


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def test_descargar_pdf_exportacion_404_si_no_existe(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.repo_exportacion.get_by_id", lambda factura_id, conn: None
    )

    with pytest.raises(HTTPException) as ei:
        asyncio.run(
            facturacion_routes.descargar_pdf_factura_exportacion(999, _fake_request(method="GET"))
        )
    assert ei.value.status_code == 404


def test_descargar_pdf_exportacion_400_si_no_emitida(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.repo_exportacion.get_by_id",
        lambda factura_id, conn: _fake_factura_exportacion("pendiente"),
    )

    with pytest.raises(HTTPException) as ei:
        asyncio.run(
            facturacion_routes.descargar_pdf_factura_exportacion(1, _fake_request(method="GET"))
        )
    assert ei.value.status_code == 400


def test_descargar_pdf_exportacion_503_si_faltan_datos_de_arca(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.repo_exportacion.get_by_id",
        lambda factura_id, conn: _fake_factura_exportacion(),
    )

    def _raise(*a, **kw):
        raise ValueError("ComprobanteFiscalExportacion incompleto, faltan: qr_url")

    monkeypatch.setattr(
        "services.facturacion.comprobante_render_exportacion.factura_exportacion_html", _raise
    )

    with pytest.raises(HTTPException) as ei:
        asyncio.run(
            facturacion_routes.descargar_pdf_factura_exportacion(1, _fake_request(method="GET"))
        )
    assert ei.value.status_code == 503


def test_descargar_pdf_exportacion_format_html_devuelve_preview_sin_renderer(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.repo_exportacion.get_by_id",
        lambda factura_id, conn: _fake_factura_exportacion(),
    )
    monkeypatch.setattr(
        "services.facturacion.comprobante_render_exportacion.factura_exportacion_html",
        lambda factura, conn: "<html>FACTURA-E-X</html>",
    )

    resp = asyncio.run(
        facturacion_routes.descargar_pdf_factura_exportacion(
            1, _fake_request(method="GET"), format="html"
        )
    )
    assert resp.status_code == 200
    assert b"FACTURA-E-X" in resp.body
