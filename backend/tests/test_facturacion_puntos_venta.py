"""Tests de services.facturacion.puntos_venta — consulta a ARCA (WSFE
FEParamGetPtosVenta) de los puntos de venta habilitados de UN emisor
concreto (a diferencia del padrón, acá el emisor se autentica con SU PROPIO
cert, no el de cualquiera)."""
from __future__ import annotations

import pytest

from services.facturacion.puntos_venta import consultar_puntos_venta

pytestmark = pytest.mark.unit


class _FakeCred:
    ambiente = "homologacion"
    cuit = 20300000000
    endpoint_wsfe = "wswhomo.afip.gov.ar"


def _patch_auth(monkeypatch):
    monkeypatch.setattr(
        "services.facturacion.config.credenciales",
        lambda emisor, conn: _FakeCred(),
    )
    monkeypatch.setattr(
        "services.facturacion.wsaa_cache.get_ta",
        lambda emisor, conn, servicio="wsfe": ("tok", "sign"),
    )


def test_filtra_bloqueados_dados_de_baja_y_no_electronicos(monkeypatch):
    _patch_auth(monkeypatch)
    monkeypatch.setattr(
        "arca_fe.wsfe.WsfeClient.param_puntos_venta",
        lambda self: [
            {"Nro": 2, "EmisionTipo": "CAE", "Bloqueado": "N", "FchBaja": None},
            {"Nro": 3, "EmisionTipo": "CAE", "Bloqueado": "S", "FchBaja": None},  # bloqueado
            {"Nro": 4, "EmisionTipo": "CAE", "Bloqueado": "N", "FchBaja": "20240101"},  # de baja
            {"Nro": 5, "EmisionTipo": "CAI", "Bloqueado": "N", "FchBaja": None},  # no electrónico
            {"Nro": 6, "EmisionTipo": "CAE", "Bloqueado": "N", "FchBaja": None},
        ],
    )

    result = consultar_puntos_venta("pablo", conn=object())

    assert result["habilitados"] == [{"nro": 2}, {"nro": 6}]
    assert result["excluidos"] == [
        {"nro": 3, "motivo": "bloqueado"},
        {"nro": 4, "motivo": "dado_de_baja"},
        {"nro": 5, "motivo": "no_electronico"},
    ]


def test_fchbaja_string_null_de_arca_no_cuenta_como_dado_de_baja(monkeypatch):
    """Regresión de bug real: la respuesta REAL de ARCA (no la del WSDL/manual) trae `FchBaja`
    como la string literal `"NULL"` para un punto de venta que NO está dado de baja — un emisor
    real reportó los 2 únicos puntos de venta que tenía, ambos activos y uno usado para emitir
    una factura con éxito, marcados igual como "dado de baja" en el diagnóstico. `"null"` en
    minúscula y con espacios también se tratan como ausente (mismo quirk, no confiar en el casing
    exacto de ARCA)."""
    _patch_auth(monkeypatch)
    monkeypatch.setattr(
        "arca_fe.wsfe.WsfeClient.param_puntos_venta",
        lambda self: [
            {"Nro": 2, "EmisionTipo": "CAE", "Bloqueado": "N", "FchBaja": "NULL"},
            {"Nro": 4, "EmisionTipo": "CAE", "Bloqueado": "N", "FchBaja": " null "},
        ],
    )

    result = consultar_puntos_venta("pablo", conn=object())

    assert result["habilitados"] == [{"nro": 2}, {"nro": 4}]
    assert result["excluidos"] == []


def test_sin_puntos_habilitados_devuelve_lista_vacia(monkeypatch):
    _patch_auth(monkeypatch)
    monkeypatch.setattr("arca_fe.wsfe.WsfeClient.param_puntos_venta", lambda self: [])

    assert consultar_puntos_venta("pablo", conn=object()) == {
        "habilitados": [],
        "excluidos": [],
    }


def test_todos_bloqueados_da_motivo_bloqueado_para_cada_uno(monkeypatch):
    _patch_auth(monkeypatch)
    monkeypatch.setattr(
        "arca_fe.wsfe.WsfeClient.param_puntos_venta",
        lambda self: [
            {"Nro": 1, "EmisionTipo": "CAE", "Bloqueado": "S", "FchBaja": None},
            {"Nro": 2, "EmisionTipo": "CAE", "Bloqueado": "S", "FchBaja": None},
        ],
    )

    result = consultar_puntos_venta("pablo", conn=object())

    assert result["habilitados"] == []
    assert result["excluidos"] == [
        {"nro": 1, "motivo": "bloqueado"},
        {"nro": 2, "motivo": "bloqueado"},
    ]


def test_emisor_sin_cert_propaga_value_error(monkeypatch):
    """`credenciales()` es la que levanta — el service no la atrapa (a
    diferencia del padrón, esto es una acción explícita del admin, no un
    autocompletado best-effort: el error tiene que llegar)."""
    def _boom(emisor, conn):
        raise ValueError("Certificado no cargado")

    monkeypatch.setattr("services.facturacion.config.credenciales", _boom)

    with pytest.raises(ValueError):
        consultar_puntos_venta("pablo", conn=object())


def test_arca_caida_propaga_arca_error(monkeypatch):
    """`param_puntos_venta()` real levanta `ArcaBusinessError`/`ArcaResponseError`
    (taxonomía tipada del motor) — `consultar_puntos_venta` ya NO la envuelve
    en `RuntimeError`: se deja pasar tal cual para que el route elija el
    status HTTP por subtipo (422/502/503) en vez de un 503 genérico."""
    from arca_fe.errores import ArcaBusinessError

    _patch_auth(monkeypatch)

    def _boom(self):
        raise ArcaBusinessError(
            "FEParamGetPtosVenta error — 600: CUIT no autorizado",
            errores=((600, "CUIT no autorizado"),),
        )

    monkeypatch.setattr("arca_fe.wsfe.WsfeClient.param_puntos_venta", _boom)

    with pytest.raises(ArcaBusinessError, match="600"):
        consultar_puntos_venta("pablo", conn=object())
