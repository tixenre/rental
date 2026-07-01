"""Tests de orquestación de services.facturacion.engine (emitir_factura / NC).

Mockea WSFE/WSAA/DB — sin red, sin Postgres real. Cubre los dos bugs
encontrados en producción:
- La idempotencia post-timeout reusaba número+CAE de la factura ANTERIOR en
  vez de pedir uno nuevo (porque consultaba `ultimo`, que por definición
  siempre está autorizado, en lugar de `ultimo + 1`).
- `emitir_nota_credito` nunca podía insertar la NC mientras la original
  seguía 'emitida' (violaba el índice único parcial por pedido_id).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from services.facturacion import engine
from services.facturacion.config import CredARCA
from services.facturacion.repo import Factura

pytestmark = pytest.mark.unit


# ── Fakes ──────────────────────────────────────────────────────────────────


class _FakeConn:
    """Conexión falsa: solo necesita tolerar SELECT/UPDATE/lock arbitrarios."""

    def __init__(self):
        self.committed = False
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

        class _R:
            def fetchone(self_inner):
                return None

            def fetchall(self_inner):
                return []

        return _R()

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class _FakeWsfe:
    """Stub de WsfeClient: registra llamadas, responde según lo configurado."""

    instances: list["_FakeWsfe"] = []

    def __init__(self, *, endpoint, cuit, token, sign):
        self.ultimo = 0
        self.consultar_resp = None
        self.solicitar_calls = []
        self.consultar_calls = []
        type(self).instances.append(self)

    def ultimo_autorizado(self, pto_vta, cbte_tipo):
        return self.ultimo

    def consultar(self, pto_vta, cbte_tipo, numero):
        self.consultar_calls.append(numero)
        return self.consultar_resp

    def solicitar_cae(self, fecae):
        self.solicitar_calls.append(fecae)
        from arca_fe import CaeResult
        return CaeResult(resultado="A", cae="86261839900001", cae_vto=date(2030, 1, 1), numero=fecae["FeDetReq"]["FECAEDetRequest"][0]["CbteDesde"])


def _fake_cred() -> CredARCA:
    return CredARCA(
        emisor_id=1,
        emisor="santini",
        condicion_iva="monotributo",
        ambiente="homologacion",
        cuit=20300000000,
        punto_venta=2,
        cert_pem=b"x",
        key_pem=b"x",
        endpoint_wsaa="https://wsaahomo.afip.gov.ar/ws/services/LoginCms",
        endpoint_wsfe="https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL",
    )


def _fake_pedido() -> dict:
    return {
        "id": 1,
        "estado": "confirmado",
        "monto_total": 5700,
        "iva_monto": 0,
        "cliente_perfil_impuestos": "consumidor_final",
        "cliente_cuit": None,
        "cliente_dni": "42289220",
        "cliente_nombre": "Ignacio Beramendi",
        "fecha_desde": "2026-06-30",
        "fecha_hasta": "2026-07-01",
        "items": [],
    }


def _patch_common(monkeypatch, wsfe_instance):
    monkeypatch.setattr(engine, "get_db", lambda: _FakeConn())
    monkeypatch.setattr(engine, "_get_pedido", lambda conn, pedido_id: _fake_pedido())
    monkeypatch.setattr(engine, "emisor_para", lambda perfil, conn: "santini")
    monkeypatch.setattr(engine, "credenciales", lambda nombre, conn: _fake_cred())
    monkeypatch.setattr(engine, "get_ta", lambda emisor, conn: ("tok", "sign"))
    monkeypatch.setattr(engine, "WsfeClient", lambda **kw: wsfe_instance)
    monkeypatch.setattr(engine, "get_factura_vigente", lambda pedido_id, conn: None)
    monkeypatch.setattr(engine, "insert_factura", lambda **kw: 99)

    calls = {}

    def _fake_update_cae(factura_id, conn, **kw):
        calls["update_cae"] = kw

    def _fake_update_error(factura_id, conn, **kw):
        calls["update_error"] = kw

    monkeypatch.setattr(engine, "update_cae", _fake_update_cae)
    monkeypatch.setattr(engine, "update_error", _fake_update_error)

    def _fake_get_by_id(factura_id, conn):
        return Factura(
            id=99, pedido_id=1, emisor="santini", ambiente="homologacion",
            cbte_tipo=11, pto_vta=2, cbte_nro=calls.get("update_cae", {}).get("cbte_nro"),
            cae=calls.get("update_cae", {}).get("cae"), cae_vto=None,
            doc_tipo=96, doc_nro="42289220", condicion_iva_receptor=5,
            concepto=2, imp_neto=5700, imp_iva=0, imp_total=5700, moneda="PES",
            cliente_cuit=None, razon_social=None, qr_payload=None, pdf_key=None,
            estado="emitida" if "update_cae" in calls else "error",
            nota_credito_de=None, raw_request=None, raw_response=None,
            errores=None, fecha_emision=None, created_at=None, created_by=None,
        )

    monkeypatch.setattr(engine, "get_by_id", _fake_get_by_id)
    return calls


# ── emitir_factura: idempotencia post-timeout ───────────────────────────────


def test_emitir_factura_pide_cae_nuevo_cuando_no_hay_recovery(monkeypatch):
    """Caso normal: `numero_a_emitir` todavía no existe en ARCA → pide un CAE nuevo."""
    wsfe = _FakeWsfe(endpoint="x", cuit=1, token="t", sign="s")
    wsfe.ultimo = 1  # ya hay una factura anterior autorizada (número 1)
    wsfe.consultar_resp = None  # numero_a_emitir=2 todavía no existe

    calls = _patch_common(monkeypatch, wsfe)

    factura = engine.emitir_factura(1)

    assert len(wsfe.solicitar_calls) == 1, "debe pedir un CAE nuevo a ARCA"
    assert wsfe.consultar_calls == [2], "debe consultar el PRÓXIMO número (2), no el último (1)"
    assert calls["update_cae"]["cbte_nro"] == 2
    assert calls["update_cae"]["cae"] == "86261839900001"


def test_emitir_factura_no_duplica_cae_de_la_factura_anterior(monkeypatch):
    """Bug de prod: NO debe reusar el CAE de la última factura autorizada.

    Si ARCA ya tiene autorizado el número `ultimo` (la factura anterior, de
    OTRO pedido), consultar(ultimo) devolvería 'A' — pero el fix consulta
    `ultimo + 1`, que legítimamente no existe todavía, así que debe pedir un
    CAE propio en vez de heredar el de la anterior.
    """
    wsfe = _FakeWsfe(endpoint="x", cuit=1, token="t", sign="s")
    wsfe.ultimo = 1
    wsfe.consultar_resp = None  # numero_a_emitir=2 no existe → no hay "recovery" espurio

    _patch_common(monkeypatch, wsfe)

    engine.emitir_factura(1)

    assert wsfe.solicitar_calls, "no debe saltear solicitar_cae confundiendo la factura anterior con la propia"


def test_emitir_factura_recupera_cae_si_su_propio_reintento_ya_autorizo(monkeypatch):
    """Timeout genuino: nuestro propio intento anterior ya autorizó `numero_a_emitir`
    en ARCA (la respuesta se perdió de nuestro lado) → se recupera, no se duplica."""
    wsfe = _FakeWsfe(endpoint="x", cuit=1, token="t", sign="s")
    wsfe.ultimo = 1
    wsfe.consultar_resp = {
        "Resultado": "A",
        "CodAutorizacion": "86261839900002",
        "CAEFchVto": "20300101",
    }

    calls = _patch_common(monkeypatch, wsfe)

    engine.emitir_factura(1)

    assert not wsfe.solicitar_calls, "no debe pedir un CAE nuevo si ya se recuperó uno"
    assert calls["update_cae"]["cbte_nro"] == 2
    assert calls["update_cae"]["cae"] == "86261839900002"


# ── emitir_nota_credito: orden anulación/insert + snapshot de importes ─────


def _fake_original_factura() -> Factura:
    return Factura(
        id=14, pedido_id=422, emisor="santini", ambiente="homologacion",
        cbte_tipo=11, pto_vta=2, cbte_nro=1, cae="86261839900000", cae_vto=None,
        doc_tipo=96, doc_nro="42289220", condicion_iva_receptor=5,
        concepto=2, imp_neto=5700, imp_iva=0, imp_total=5700, moneda="PES",
        cliente_cuit=None, razon_social=None, qr_payload=None, pdf_key=None,
        estado="emitida", nota_credito_de=None, raw_request=None,
        raw_response=None, errores=None, fecha_emision=None,
        created_at=None, created_by=None,
    )


def test_emitir_nota_credito_anula_original_antes_de_insertar(monkeypatch):
    """Bug de prod: insertar la NC mientras la original sigue 'emitida' viola
    uq_factura_vigente_por_pedido. `marcar_anulada` debe correr ANTES del insert."""
    wsfe = _FakeWsfe(endpoint="x", cuit=1, token="t", sign="s")
    wsfe.ultimo = 1

    order = []
    monkeypatch.setattr(engine, "get_db", lambda: _FakeConn())
    monkeypatch.setattr(engine, "_get_pedido", lambda conn, pedido_id: _fake_pedido())
    monkeypatch.setattr(engine, "get_by_id", lambda factura_id, conn: _fake_original_factura())
    monkeypatch.setattr(engine, "credenciales", lambda nombre, conn: _fake_cred())
    monkeypatch.setattr(engine, "get_ta", lambda emisor, conn: ("tok", "sign"))
    monkeypatch.setattr(engine, "WsfeClient", lambda **kw: wsfe)
    monkeypatch.setattr(engine, "marcar_anulada", lambda factura_id, conn: order.append("anular"))
    monkeypatch.setattr(engine, "insert_factura", lambda **kw: order.append("insert") or 200)
    monkeypatch.setattr(engine, "update_cae", lambda *a, **kw: None)
    monkeypatch.setattr(engine, "update_error", lambda *a, **kw: None)
    monkeypatch.setattr(engine, "revertir_anulacion", lambda *a, **kw: order.append("revertir"))

    engine.emitir_nota_credito(14)

    assert order[0] == "anular", "la original tiene que anularse ANTES de insertar la NC"
    assert order[1] == "insert"
    assert "revertir" not in order, "ARCA aprobó → no debe revertir la anulación"


def test_emitir_nota_credito_revierte_anulacion_si_arca_rechaza(monkeypatch):
    """Si ARCA rechaza la NC, la original nunca se anuló de verdad → revertir."""
    wsfe = _FakeWsfe(endpoint="x", cuit=1, token="t", sign="s")
    wsfe.ultimo = 1

    def _rechazo(fecae):
        from arca_fe import CaeResult
        return CaeResult(resultado="R", errores=("10: rechazado",))

    wsfe.solicitar_cae = _rechazo

    order = []
    monkeypatch.setattr(engine, "get_db", lambda: _FakeConn())
    monkeypatch.setattr(engine, "_get_pedido", lambda conn, pedido_id: _fake_pedido())
    monkeypatch.setattr(engine, "get_by_id", lambda factura_id, conn: _fake_original_factura())
    monkeypatch.setattr(engine, "credenciales", lambda nombre, conn: _fake_cred())
    monkeypatch.setattr(engine, "get_ta", lambda emisor, conn: ("tok", "sign"))
    monkeypatch.setattr(engine, "WsfeClient", lambda **kw: wsfe)
    monkeypatch.setattr(engine, "marcar_anulada", lambda factura_id, conn: order.append("anular"))
    monkeypatch.setattr(engine, "insert_factura", lambda **kw: 200)
    monkeypatch.setattr(engine, "update_cae", lambda *a, **kw: order.append("update_cae"))
    monkeypatch.setattr(engine, "update_error", lambda *a, **kw: order.append("update_error"))
    monkeypatch.setattr(engine, "revertir_anulacion", lambda *a, **kw: order.append("revertir"))

    engine.emitir_nota_credito(14)

    assert "update_cae" not in order
    assert order[-1] == "revertir", "ARCA rechazó → la anulación se tiene que revertir"


def test_construir_comprobante_nc_usa_snapshot_no_pedido_en_vivo():
    """El importe de la NC tiene que salir de la factura original persistida,
    no recalcularse del pedido (que puede haber cambiado de precio/descuento)."""
    from services.facturacion.comprobante_pedido import construir_comprobante_nc
    from arca_fe import Emisor, CondicionIva, CbteAsoc, CbteTipo

    original = _fake_original_factura()
    # El pedido "en vivo" ahora tiene un monto MUY distinto al facturado.
    pedido_con_precio_cambiado = {**_fake_pedido(), "monto_total": 999999, "iva_monto": 0}
    emisor_obj = Emisor(cuit=20300000000, punto_venta=2, condicion_iva=CondicionIva.MONOTRIBUTO)
    cbte_asoc = CbteAsoc(tipo=CbteTipo.FACTURA_C, punto_venta=2, numero=1)

    req = construir_comprobante_nc(
        original, pedido_con_precio_cambiado, emisor_obj,
        fecha=date(2026, 7, 1), cbtes_asoc=(cbte_asoc,),
    )

    assert req.importe_neto == Decimal(original.imp_neto), (
        "la NC tiene que cancelar el monto de la factura ORIGINAL, no el pedido en vivo"
    )
