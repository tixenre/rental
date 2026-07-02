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

    def commit(self):
        pass


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
        ("POST", "/api/admin/arca/catalogos/refrescar"),
        ("GET", "/api/admin/emisores-arca"),
        ("POST", "/api/admin/emisores-arca"),
        ("PUT", "/api/admin/emisores-arca/1"),
        ("DELETE", "/api/admin/emisores-arca/1"),
        ("POST", "/api/admin/emisores-arca/1/cert"),
        ("GET", "/api/admin/emisores-arca/1/puntos-venta"),
        ("GET", "/api/admin/arca/padron/20301234567"),
        ("GET", "/api/alquileres/1/facturar/preview"),
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


# ── preview_factura: arma sin emitir, ValueError → 400 ──────────────────────


def test_preview_factura_devuelve_el_armado(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.engine.previsualizar_factura",
        lambda pedido_id, conn: {"comprobante": {"letra": "C"}},
    )

    result = facturacion_routes.preview_factura(1, _fake_request())
    assert result == {"comprobante": {"letra": "C"}}


def test_preview_factura_value_error_es_400(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.engine.previsualizar_factura",
        lambda pedido_id, conn: (_ for _ in ()).throw(ValueError("no confirmado")),
    )
    with pytest.raises(HTTPException) as ei:
        facturacion_routes.preview_factura(1, _fake_request())
    assert ei.value.status_code == 400


def test_preview_factura_runtime_error_es_503_nunca_500(monkeypatch):
    """El preview llama a ARCA (FECompUltimoAutorizado) — si ARCA está caída
    o el cert venció, tiene que ser 503, no un 500 crudo."""
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.engine.previsualizar_factura",
        lambda pedido_id, conn: (_ for _ in ()).throw(RuntimeError("ARCA caída")),
    )
    with pytest.raises(HTTPException) as ei:
        facturacion_routes.preview_factura(1, _fake_request())
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


def test_descargar_pdf_503_si_faltan_datos_de_arca(monkeypatch):
    """factura_html falla fuerte (RuntimeError) si a una 'emitida' le faltan
    datos de ARCA — el route lo convierte en 503, nunca en un 500 crudo."""
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.repo.get_by_id", lambda factura_id, conn: _fake_factura()
    )
    monkeypatch.setattr(
        "services.facturacion.engine._get_pedido", lambda conn, pedido_id: {"id": pedido_id}
    )

    def _raise(*a, **kw):
        raise RuntimeError("Factura 1 está 'emitida' pero le faltan datos de ARCA (qr_payload)")

    monkeypatch.setattr("services.facturacion.pdf.factura_html", _raise)

    with pytest.raises(HTTPException) as ei:
        asyncio.run(facturacion_routes.descargar_pdf_factura(1, _fake_request()))
    assert ei.value.status_code == 503


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
    monkeypatch.setattr(
        "services.facturacion.pdf_seguridad.get_or_create_signing_cert",
        lambda conn: (b"cert", b"key"),
    )
    monkeypatch.setattr(
        "services.facturacion.pdf_seguridad.asegurar_pdf",
        lambda pdf_bytes, cert_pem, key_pem: pdf_bytes,
    )

    resp = asyncio.run(facturacion_routes.descargar_pdf_factura(1, _fake_request()))
    assert resp.status_code == 200
    assert resp.body == b"%PDF-FAKE%"
    assert "attachment" in resp.headers["content-disposition"]
    assert "Factura-C-00002-00000001.pdf" in resp.headers["content-disposition"]


# ── consultar_padron: autocompletar CUIT — nunca rompe, {encontrado: false} ─


def test_consultar_padron_encontrado(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())

    class _Persona:
        razon_social = "Empresa XYZ SRL"
        nombre = ""
        apellido = ""
        domicilio = "Ruta 88 km 12"
        condicion_iva = "responsable_inscripto"
        estado_clave = "ACTIVO"

    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona",
        lambda cuit, conn: _Persona(),
    )

    result = facturacion_routes.consultar_padron("30712345678", _fake_request())
    assert result == {
        "encontrado": True,
        "razon_social": "Empresa XYZ SRL",
        "nombre": "",
        "apellido": "",
        "domicilio": "Ruta 88 km 12",
        "condicion_iva": "responsable_inscripto",
        "estado_clave": "ACTIVO",
    }


def test_consultar_padron_no_encontrado_no_es_error(monkeypatch):
    """AFIP caído / sin datos / sin emisor autenticador — nunca un error, el
    formulario sigue siendo editable a mano."""
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.padron.resolver_persona", lambda cuit, conn: None
    )

    result = facturacion_routes.consultar_padron("30712345678", _fake_request())
    assert result == {"encontrado": False}


# ── consultar_puntos_venta_emisor: validar/elegir en vez de cargar a mano ───


def _fake_emisor_arca(nombre="pablo"):
    from datetime import datetime
    from services.facturacion.emisores_repo import EmisorArca

    return EmisorArca(
        id=1, nombre=nombre, cuit="20300000000", pto_vta=2,
        condicion_iva="responsable_inscripto", cert_cargado=True,
        activo=True, razon_social=None, domicilio=None, iibb=None,
        inicio_actividades=None, notas=None,
        created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
    )


def test_consultar_puntos_venta_devuelve_lista(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.get_by_id",
        lambda emisor_id, conn: _fake_emisor_arca(),
    )
    monkeypatch.setattr(
        "services.facturacion.puntos_venta.consultar_puntos_venta",
        lambda nombre_emisor, conn: [{"nro": 2}, {"nro": 5}],
    )

    result = facturacion_routes.consultar_puntos_venta_emisor(1, _fake_request())
    assert result == {"puntos_venta": [{"nro": 2}, {"nro": 5}]}


def test_consultar_puntos_venta_emisor_no_encontrado_es_404(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.get_by_id", lambda emisor_id, conn: None
    )

    with pytest.raises(HTTPException) as exc:
        facturacion_routes.consultar_puntos_venta_emisor(1, _fake_request())
    assert exc.value.status_code == 404


def test_consultar_puntos_venta_sin_cert_es_400(monkeypatch):
    """Emisor existe pero no tiene cert cargado — `credenciales()` (dentro
    del service) levanta ValueError; la route lo mapea a 400, no a 500."""
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.get_by_id",
        lambda emisor_id, conn: _fake_emisor_arca(),
    )

    def _boom(nombre_emisor, conn):
        raise ValueError("Certificado no cargado")

    monkeypatch.setattr("services.facturacion.puntos_venta.consultar_puntos_venta", _boom)

    with pytest.raises(HTTPException) as exc:
        facturacion_routes.consultar_puntos_venta_emisor(1, _fake_request())
    assert exc.value.status_code == 400


def test_consultar_puntos_venta_arca_caida_es_503_nunca_500(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.emisores_repo.get_by_id",
        lambda emisor_id, conn: _fake_emisor_arca(),
    )

    def _boom(nombre_emisor, conn):
        raise RuntimeError("WSAA no respondió")

    monkeypatch.setattr("services.facturacion.puntos_venta.consultar_puntos_venta", _boom)

    with pytest.raises(HTTPException) as exc:
        facturacion_routes.consultar_puntos_venta_emisor(1, _fake_request())
    assert exc.value.status_code == 503


# ── refrescar_catalogos_arca: actualiza las etiquetas del PDF desde ARCA ────


def test_refrescar_catalogos_arca_devuelve_conteos(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        "services.facturacion.catalogos.refrescar_catalogos",
        lambda conn: {
            "doc_tipo": [{"id": 80, "desc": "CUIT"}],
            "concepto": [{"id": 1, "desc": "Productos"}, {"id": 2, "desc": "Servicios"}],
            "condicion_iva_receptor": [],
        },
    )

    result = facturacion_routes.refrescar_catalogos_arca(_fake_request())
    assert result == {"ok": True, "doc_tipo": 1, "concepto": 2, "condicion_iva_receptor": 0}


def test_refrescar_catalogos_arca_sin_emisor_es_400(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())

    def _boom(conn):
        raise ValueError("No hay ningún emisor activo con certificado cargado")

    monkeypatch.setattr("services.facturacion.catalogos.refrescar_catalogos", _boom)

    with pytest.raises(HTTPException) as exc:
        facturacion_routes.refrescar_catalogos_arca(_fake_request())
    assert exc.value.status_code == 400


def test_refrescar_catalogos_arca_caida_es_503(monkeypatch):
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())

    def _boom(conn):
        raise RuntimeError("FEParamGetTiposDoc error")

    monkeypatch.setattr("services.facturacion.catalogos.refrescar_catalogos", _boom)

    with pytest.raises(HTTPException) as exc:
        facturacion_routes.refrescar_catalogos_arca(_fake_request())
    assert exc.value.status_code == 503
