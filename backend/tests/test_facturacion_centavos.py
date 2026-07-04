"""Regresión bug #1209: `facturas.imp_neto/imp_iva/imp_total` NO deben truncarse
a peso entero. El CAE/QR de ARCA autorizan el importe EXACTO al centavo — si la
fila persistida (y por lo tanto el PDF impreso) redondea, el comprobante fiscal
impreso queda por debajo de lo que ARCA realmente autorizó. Reproduce el
escenario del issue: Factura A (RI), neto=$1001 (no múltiplo de 100) → IVA 21%
da $210,21 (con centavos), no $210.

Mockea WSFE/WSAA/DB — sin red, sin Postgres real (mismo patrón que
test_facturacion_engine.py).
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from services.facturacion import engine
from services.facturacion.config import CredARCA
from services.facturacion.repo import Factura

pytestmark = pytest.mark.unit

# Catálogos ARCA (doc_tipo/condición IVA receptor) resueltos vía `database.get_db`
# desde `services.facturacion.pdf._catalogo` — mismo fake que `test_facturacion_pdf.py`.
_CATALOGOS_SEED = {
    "arca_catalogo_doc_tipo": [{"id": 80, "desc": "CUIT"}],
    "arca_catalogo_concepto": [{"id": 2, "desc": "Servicios"}],
    "arca_catalogo_condicion_iva_receptor": [{"id": 1, "desc": "IVA Responsable Inscripto"}],
}


class _FakeCatalogConn:
    def execute(self, sql, params=None):
        key = params[0] if params else None
        value = json.dumps(_CATALOGOS_SEED[key]) if key in _CATALOGOS_SEED else None

        class _R:
            def fetchone(self_inner):
                return {"value": value} if value is not None else None

        return _R()

    def close(self):
        pass


class _FakeConn:
    def execute(self, sql, params=None):
        class _R:
            def fetchone(self_inner):
                return None

            def fetchall(self_inner):
                return []

        return _R()

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class _FakeWsfe:
    def __init__(self, *, endpoint, cuit, token, sign):
        self.ultimo = 0
        self.consultar_resp = None
        self.solicitar_calls = []

    def ultimo_autorizado(self, pto_vta, cbte_tipo):
        return self.ultimo

    def consultar(self, pto_vta, cbte_tipo, numero):
        return self.consultar_resp

    def solicitar_cae(self, fecae):
        self.solicitar_calls.append(fecae)
        from arca_fe import CaeResult
        return CaeResult(
            resultado="A", cae="86261839900099", cae_vto=date(2030, 1, 1),
            numero=fecae["FeDetReq"]["FECAEDetRequest"][0]["CbteDesde"],
        )


def _fake_cred_ri() -> CredARCA:
    """Emisor Responsable Inscripto (Pablo) → Factura A con IVA discriminado."""
    return CredARCA(
        emisor_id=1,
        emisor="pablo",
        condicion_iva="responsable_inscripto",
        ambiente="homologacion",
        cuit=20111111112,
        punto_venta=3,
        cert_pem=b"x",
        key_pem=b"x",
        endpoint_wsaa="https://wsaahomo.afip.gov.ar/ws/services/LoginCms",
        endpoint_wsfe="https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL",
    )


def _fake_pedido_neto_impar() -> dict:
    """Neto=$1001 (no múltiplo de 100) + receptor RI → IVA 21% da $210,21."""
    return {
        "id": 42,
        "cliente_id": 42,
        "estado": "confirmado",
        "monto_total": 1001,
        "iva_monto": 210,  # ya viene aproximado en el pedido; el motor recalcula exacto
        "cliente_perfil_impuestos": "responsable_inscripto",
        "cliente_cuit": "20300000000",
        "cliente_dni": None,
        "cliente_razon_social": "Cliente RI SA",
        "cliente_nombre": "Cliente RI SA",
        "fecha_desde": "2026-07-01",
        "fecha_hasta": "2026-07-02",
        "items": [],
    }


def test_emitir_factura_persiste_centavos_exactos_no_trunca(monkeypatch):
    """imp_neto/imp_iva/imp_total persistidos == Decimal exacto mandado a ARCA."""
    wsfe = _FakeWsfe(endpoint="x", cuit=1, token="t", sign="s")

    captured_insert = {}

    def _fake_insert_factura(**kw):
        captured_insert.update(kw)
        return 500

    captured_update = {}

    def _fake_update_cae(factura_id, conn, **kw):
        captured_update.update(kw)

    monkeypatch.setattr(engine, "get_db", lambda: _FakeConn())
    monkeypatch.setattr(engine, "_get_pedido", lambda conn, pedido_id: _fake_pedido_neto_impar())
    monkeypatch.setattr(engine, "emisor_para", lambda perfil, conn: "pablo")
    monkeypatch.setattr(engine, "credenciales", lambda nombre, conn: _fake_cred_ri())
    monkeypatch.setattr(engine, "get_ta", lambda emisor, conn: ("tok", "sign"))
    monkeypatch.setattr(engine, "WsfeClient", lambda **kw: wsfe)
    monkeypatch.setattr(engine, "get_factura_vigente", lambda pedido_id, conn: None)

    from arca_fe.padron import PersonaArca

    monkeypatch.setattr(
        engine,
        "verificar_y_actualizar_receptor",
        lambda cuit, cliente_id, conn: PersonaArca(
            cuit=cuit, razon_social="Cliente RI SA", nombre="", apellido="",
            domicilio="", condicion_iva="responsable_inscripto", estado_clave="ACTIVO",
        ),
    )
    monkeypatch.setattr(engine, "insert_factura", _fake_insert_factura)
    monkeypatch.setattr(engine, "update_cae", _fake_update_cae)
    monkeypatch.setattr(engine, "update_error", lambda *a, **kw: None)
    monkeypatch.setattr(
        engine, "get_by_id",
        lambda factura_id, conn: Factura(
            id=500, pedido_id=42, emisor="pablo", ambiente="homologacion",
            cbte_tipo=1, pto_vta=3, cbte_nro=captured_update.get("cbte_nro"),
            cae=captured_update.get("cae"), cae_vto=None,
            doc_tipo=80, doc_nro="20300000000", condicion_iva_receptor=1,
            concepto=2, imp_neto=captured_insert.get("imp_neto"),
            imp_iva=captured_insert.get("imp_iva"), imp_total=captured_insert.get("imp_total"),
            moneda="PES", cliente_cuit="20300000000", razon_social="Cliente RI SA",
            qr_payload=None, pdf_key=None, estado="emitida", nota_credito_de=None,
            raw_request=None, raw_response=None, errores=None, fecha_emision=None,
            created_at=None, created_by=None,
        ),
    )

    factura = engine.emitir_factura(42)

    # Lo que se mandó a ARCA (FECAESolicitar) — al centavo.
    det = wsfe.solicitar_calls[0]["FeDetReq"]["FECAEDetRequest"][0]
    assert det["ImpNeto"] == "1001.00"
    assert det["ImpIVA"] == "210.21"
    assert det["ImpTotal"] == "1211.21"

    # Lo que se persistió en `facturas` — TIENE que ser el mismo valor exacto,
    # no truncado a entero (bug #1209: guardaba imp_iva=210, imp_total=1211).
    assert captured_insert["imp_neto"] == Decimal("1001.00")
    assert captured_insert["imp_iva"] == Decimal("210.21")
    assert captured_insert["imp_total"] == Decimal("1211.21")

    # Y lo que devuelve la factura emitida (lo que ve el PDF/admin) coincide.
    assert factura.imp_iva == Decimal("210.21")
    assert factura.imp_total == Decimal("1211.21")


def test_pdf_muestra_centavos_no_redondea_a_peso_entero(monkeypatch):
    """El PDF de una factura con centavos los tiene que mostrar, no truncarlos.

    `pdf._money`/`_plain` ya formatean con `.2f` — el bug estaba 100% en la
    persistencia (engine.py), no en el render; este test lo confirma end-to-end
    con los valores exactos que hubiera dejado el escenario de arriba.
    """
    monkeypatch.setattr("database.get_db", lambda: _FakeCatalogConn())
    from services.facturacion.pdf import factura_html

    factura = Factura(
        id=500, pedido_id=42, emisor="pablo", ambiente="homologacion",
        cbte_tipo=1, pto_vta=3, cbte_nro=7, cae="86261839900099",
        cae_vto=date(2030, 1, 1), doc_tipo=80, doc_nro="20300000000",
        condicion_iva_receptor=1, concepto=2,
        imp_neto=Decimal("1001.00"), imp_iva=Decimal("210.21"), imp_total=Decimal("1211.21"),
        moneda="PES", cliente_cuit="20300000000", razon_social="Cliente RI SA",
        qr_payload="https://www.afip.gob.ar/fe/qr/?p=abc", pdf_key=None,
        estado="emitida", nota_credito_de=None, raw_request=None, raw_response=None,
        errores=None, fecha_emision=None, created_at=None, created_by=None,
    )
    pedido = {
        "id": 42, "monto_total": 1001, "monto_pagado": 0,
        "cliente_nombre": "Cliente RI SA", "cliente_domicilio_fiscal": "Falsa 123",
        "fecha_desde": "2026-07-01", "fecha_hasta": "2026-07-02", "items": [],
    }

    html = factura_html(factura, pedido)

    assert "210,21" in html, "el IVA con centavos no se muestra en el PDF"
    assert "1.211,21" in html, "el total con centavos no se muestra en el PDF"
    # Nunca el importe truncado a peso entero que dejaba el bug #1209.
    assert "210,00" not in html
    assert "1.211,00" not in html
