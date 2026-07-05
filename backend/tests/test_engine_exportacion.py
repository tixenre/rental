"""Tests de orquestación de services.facturacion.engine_exportacion (WSFEXv1).

Mockea WSFEX/WSAA/DB — sin red, sin Postgres real. Mismo criterio que
test_facturacion_engine.py: cubre idempotencia post-timeout (consultar el PRÓXIMO número, no el
último autorizado) y el gate de habilitado_exportacion."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from services.facturacion import engine_exportacion
from services.facturacion.config import CredARCA
from services.facturacion.emisores_repo import EmisorArca
from services.facturacion.repo_exportacion import FacturaExportacion

pytestmark = pytest.mark.unit


class _FakeConn:
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


class _FakeWsfex:
    instances: list["_FakeWsfex"] = []

    def __init__(self, *, endpoint, cuit, token, sign):
        self.ultimo = 0
        self.consultar_resp = None
        self.autorizar_calls = []
        self.consultar_calls = []
        type(self).instances.append(self)

    def ultimo_autorizado(self, pto_vta, cbte_tipo):
        return self.ultimo

    def consultar(self, pto_vta, cbte_tipo, numero):
        self.consultar_calls.append(numero)
        return self.consultar_resp

    def autorizar(self, comprobante, numero):
        self.autorizar_calls.append((comprobante, numero))
        from arca_fe import CaeResult
        return CaeResult(resultado="A", cae="70012345670001", cae_vto=date(2030, 1, 1), numero=numero)


def _fake_emisor_row(habilitado_exportacion=True) -> EmisorArca:
    from datetime import datetime

    return EmisorArca(
        id=1, nombre="santini", cuit="20300000003", pto_vta=2,
        condicion_iva="monotributo", cert_cargado=True, activo=True,
        razon_social=None, domicilio=None, iibb=None, inicio_actividades=None,
        notas=None, created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
        habilitado_exportacion=habilitado_exportacion,
    )


def _fake_cred() -> CredARCA:
    return CredARCA(
        emisor_id=1, emisor="santini", condicion_iva="monotributo", ambiente="homologacion",
        cuit=20300000003, punto_venta=2, cert_pem=b"x", key_pem=b"x",
        endpoint_wsaa="https://wsaahomo.afip.gov.ar/ws/services/LoginCms",
        endpoint_wsfe="https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL",
        endpoint_wsfex="https://wswhomo.afip.gov.ar/wsfexv1/service.asmx?WSDL",
    )


def _fake_comprobante():
    from arca_fe.modelos import CondicionIva, Concepto, Emisor
    from arca_fe.modelos_exportacion import ComprobanteExportacionRequest, DatosExportacion, ReceptorExterior

    emisor = Emisor(cuit=20300000003, punto_venta=2, condicion_iva=CondicionIva.MONOTRIBUTO)
    receptor = ReceptorExterior(razon_social="Acme Corp", pais_destino_id=203)
    exportacion = DatosExportacion(incoterm="FOB", permiso_embarque="X")
    return ComprobanteExportacionRequest(
        emisor=emisor, receptor=receptor, exportacion=exportacion, concepto=Concepto.PRODUCTOS,
        importe_neto=Decimal("1000.00"), fecha=date(2026, 7, 1), moneda="USD",
        cotizacion=Decimal("1000"),
    )


def _patch_common(monkeypatch, wsfex_instance, *, habilitado_exportacion=True):
    monkeypatch.setattr(engine_exportacion, "get_db", lambda: _FakeConn())
    monkeypatch.setattr(
        engine_exportacion, "get_by_nombre",
        lambda nombre, conn: _fake_emisor_row(habilitado_exportacion),
    )
    monkeypatch.setattr(engine_exportacion, "credenciales", lambda nombre, conn: _fake_cred())
    monkeypatch.setattr(
        engine_exportacion, "get_ta", lambda emisor, conn, servicio=None: ("tok", "sign")
    )
    monkeypatch.setattr(engine_exportacion, "WsfexClient", lambda **kw: wsfex_instance)
    monkeypatch.setattr(engine_exportacion, "insert_factura_exportacion", lambda **kw: 99)

    calls = {}

    def _fake_update_cae(factura_id, conn, **kw):
        calls["update_cae"] = kw

    def _fake_update_error(factura_id, conn, **kw):
        calls["update_error"] = kw

    monkeypatch.setattr(engine_exportacion, "update_cae_exportacion", _fake_update_cae)
    monkeypatch.setattr(engine_exportacion, "update_error_exportacion", _fake_update_error)

    def _fake_get_by_id(factura_id, conn):
        return FacturaExportacion(
            id=99, emisor="santini", ambiente="homologacion", cbte_tipo=19, pto_vta=2,
            cbte_nro=calls.get("update_cae", {}).get("cbte_nro"),
            cae=calls.get("update_cae", {}).get("cae"), cae_vto=None,
            receptor_razon_social="Acme Corp", receptor_pais_destino=203,
            receptor_domicilio=None, receptor_id_impositivo=None,
            incoterm="FOB", permiso_embarque="X", moneda="USD", cotizacion=Decimal("1000"),
            imp_total=Decimal("1000.00"),
            estado="emitida" if "update_cae" in calls else "error",
            nota_credito_de=None, qr_payload=calls.get("update_cae", {}).get("qr_payload"),
            raw_request=None, raw_response=None,
            errores=None, fecha_emision=None, created_at=None, created_by=None,
        )

    monkeypatch.setattr(engine_exportacion, "get_by_id", _fake_get_by_id)
    return calls


def test_emitir_factura_exportacion_pide_cae_nuevo_cuando_no_hay_recovery(monkeypatch):
    wsfex = _FakeWsfex(endpoint="x", cuit=1, token="t", sign="s")
    wsfex.ultimo = 1
    wsfex.consultar_resp = None

    calls = _patch_common(monkeypatch, wsfex)

    factura = engine_exportacion.emitir_factura_exportacion("santini", _fake_comprobante())

    assert len(wsfex.autorizar_calls) == 1, "debe pedir un CAE nuevo a ARCA"
    assert wsfex.consultar_calls == [2], "debe consultar el PRÓXIMO número (2), no el último (1)"
    assert calls["update_cae"]["cbte_nro"] == 2
    assert calls["update_cae"]["cae"] == "70012345670001"
    assert calls["update_cae"]["qr_payload"].startswith("https://www.afip.gob.ar/fe/qr/?p=")
    assert factura.estado == "emitida"


def test_emitir_factura_exportacion_no_duplica_cae_de_la_anterior(monkeypatch):
    """Mismo bug de prod que WSFEv1: NO debe reusar el CAE de la última factura autorizada."""
    wsfex = _FakeWsfex(endpoint="x", cuit=1, token="t", sign="s")
    wsfex.ultimo = 1
    wsfex.consultar_resp = {"Resultado": "A", "Cae": "70099999990000"}

    calls = _patch_common(monkeypatch, wsfex)
    engine_exportacion.emitir_factura_exportacion("santini", _fake_comprobante())

    # numero_a_emitir=2 "existe" en la consulta fake (recuperado) → NO pide un CAE nuevo,
    # recupera el de la consulta (idempotencia post-timeout, no un CAE distinto por error).
    assert wsfex.consultar_calls == [2]
    assert calls["update_cae"]["cae"] == "70099999990000"
    assert len(wsfex.autorizar_calls) == 0, "no debe pedir un CAE nuevo si ya se recuperó uno"


def test_emisor_no_habilitado_para_exportacion_falla_temprano(monkeypatch):
    wsfex = _FakeWsfex(endpoint="x", cuit=1, token="t", sign="s")
    _patch_common(monkeypatch, wsfex, habilitado_exportacion=False)

    with pytest.raises(ValueError, match="no está habilitado para exportación"):
        engine_exportacion.emitir_factura_exportacion("santini", _fake_comprobante())

    assert len(wsfex.autorizar_calls) == 0, "no debe llegar a llamar a ARCA"


def test_emisor_no_encontrado_falla(monkeypatch):
    monkeypatch.setattr(engine_exportacion, "get_db", lambda: _FakeConn())
    monkeypatch.setattr(engine_exportacion, "get_by_nombre", lambda nombre, conn: None)

    with pytest.raises(ValueError, match="no encontrado"):
        engine_exportacion.emitir_factura_exportacion("inexistente", _fake_comprobante())


def test_rechazo_de_arca_marca_error_no_lanza_500(monkeypatch):
    wsfex = _FakeWsfex(endpoint="x", cuit=1, token="t", sign="s")
    wsfex.ultimo = 0
    wsfex.consultar_resp = None

    from arca_fe import CaeResult

    def _autorizar_rechazado(comprobante, numero):
        return CaeResult(resultado="R", errores=("500: CUIT no habilitado",))

    wsfex.autorizar = _autorizar_rechazado
    calls = _patch_common(monkeypatch, wsfex)

    factura = engine_exportacion.emitir_factura_exportacion("santini", _fake_comprobante())

    assert "update_error" in calls
    assert factura.estado == "error"
