"""Tests HTTP/contrato de routes/facturacion.py — transporte fino.

La lógica de negocio vive en services/facturacion/engine.py (testeada en
test_facturacion_engine.py); acá se clava el contrato del handler: guard de
admin a nivel HTTP (rutea + gatea, sin DB — mismo patrón que
test_clientes_merge_route.py), mapeo de errores (ValueError→400,
RuntimeError→503), y los branches format=html/pdf del PDF on-demand.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

import main
from routes import facturacion as facturacion_routes
from services.facturacion.repo import Factura

pytestmark = pytest.mark.unit

_http = TestClient(main.app, raise_server_exceptions=False)


def _fake_request() -> Request:
    """Request real (mínimo, sin transporte ASGI) — no un SimpleNamespace: los
    endpoints de escritura ahora llevan @limiter.limit (#1209), y slowapi exige
    `isinstance(request, Request)`. `request.state.session` queda sin setear
    (mismo resultado que antes: `getattr(..., "session", None)` → None)."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "raw_path": b"/x",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


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


# ── Rate limit + mapeo de errores en escrituras de facturación (#1209) ─────
#
# Antes de esta auditoría, los endpoints de escritura de facturación (facturar
# pedido, NC, enviar mail, CRUD de emisores) no llevaban @limiter.limit ni
# @map_pg_errors — a diferencia del resto de la superficie de escritura de
# plata (contabilidad.py, pagos.py, reportes.py), que ya los tenía desde la
# auditoría 2026-07-02 (#1184).


def _make_facturacion_app():
    """App mínima con SOLO el router de facturación + el limiter compartido
    (mismo patrón que test_rate_limit.py::_make_app — evita el thread de init
    de DB de main.py)."""
    from fastapi import FastAPI
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from rate_limit import limiter

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(facturacion_routes.router, prefix="/api")
    return app


def test_crear_emisor_corta_con_429_tras_exceder_admin_write_limit(monkeypatch):
    """ADMIN_WRITE_LIMIT = 60/minute: un loop contra un endpoint de escritura de
    facturación corta con 429 en vez de seguir pegándole a Postgres/ARCA sin
    freno. IP dedicada (distinta de la default "testclient" de TestClient) para
    no compartir bucket del limiter con otros tests de este archivo que golpean
    el mismo endpoint (el gate de admin, la prueba de nombre duplicado)."""
    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    client = TestClient(_make_facturacion_app(), client=("203.0.113.9", 51000))

    codes = [
        client.post("/api/admin/emisores-arca", json={}).status_code for _ in range(65)
    ]
    assert codes.count(429) >= 1, codes
    assert codes[0] == 400  # body vacío → 400 de validación, ya pasó el limiter


def test_crear_emisor_nombre_duplicado_da_400_no_500(monkeypatch):
    """`nombre` en `emisores_arca` es UNIQUE: un choque debe traducirse a 400
    limpio vía @map_pg_errors, no subir crudo como 500 con el mensaje interno
    de Postgres (constraint/columna) — el bug que motivó #1209."""
    import psycopg.errors

    monkeypatch.setattr("routes.facturacion.require_admin", lambda request: None)
    monkeypatch.setattr("routes.facturacion.get_db", lambda: _FakeConn())

    def _raise_unique(*_a, **_kw):
        raise psycopg.errors.UniqueViolation(
            'duplicate key value violates unique constraint "emisores_arca_nombre_key"'
        )

    monkeypatch.setattr("services.facturacion.emisores_repo.create_emisor", _raise_unique)

    body = {
        "nombre": "santini",
        "cuit": "20111111112",
        "pto_vta": 3,
        "condicion_iva": "monotributo",
    }
    with pytest.raises(HTTPException) as ei:
        facturacion_routes.crear_emisor(_fake_request(), body)

    assert ei.value.status_code == 400
    assert ei.value.detail == "Ya existe un registro con ese valor."
    assert "constraint" not in ei.value.detail.lower()
