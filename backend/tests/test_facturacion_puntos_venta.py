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

    assert result == [{"nro": 2}, {"nro": 6}]


def test_sin_puntos_habilitados_devuelve_lista_vacia(monkeypatch):
    _patch_auth(monkeypatch)
    monkeypatch.setattr("arca_fe.wsfe.WsfeClient.param_puntos_venta", lambda self: [])

    assert consultar_puntos_venta("pablo", conn=object()) == []


def test_emisor_sin_cert_propaga_value_error(monkeypatch):
    """`credenciales()` es la que levanta — el service no la atrapa (a
    diferencia del padrón, esto es una acción explícita del admin, no un
    autocompletado best-effort: el error tiene que llegar)."""
    def _boom(emisor, conn):
        raise ValueError("Certificado no cargado")

    monkeypatch.setattr("services.facturacion.config.credenciales", _boom)

    with pytest.raises(ValueError):
        consultar_puntos_venta("pablo", conn=object())


def test_arca_caida_propaga_runtime_error(monkeypatch):
    """Regresión: `param_puntos_venta()` real levanta `ArcaBusinessError`/
    `ArcaResponseError` (taxonomía tipada del motor), NO `RuntimeError`
    directamente — mockear un RuntimeError acá no ejercita la traducción real
    y daba falsa confianza (bug real: sin el `except ArcaError` en
    `consultar_puntos_venta`, esto escapaba como 500 sin manejar, no 503)."""
    from arca_fe.errores import ArcaBusinessError

    _patch_auth(monkeypatch)

    def _boom(self):
        raise ArcaBusinessError(
            "FEParamGetPtosVenta error — 600: CUIT no autorizado",
            errores=((600, "CUIT no autorizado"),),
        )

    monkeypatch.setattr("arca_fe.wsfe.WsfeClient.param_puntos_venta", _boom)

    with pytest.raises(RuntimeError):
        consultar_puntos_venta("pablo", conn=object())
