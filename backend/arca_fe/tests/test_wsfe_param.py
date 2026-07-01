"""Tests del cliente WSFEv1 — sin red.

Prueba el parseo de fechas, la normalización del endpoint, y la lógica de parseo
de respuestas CAE (éxito y rechazo) con objetos mock en vez de llamadas SOAP reales.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Tests de _parse_fecha
# ---------------------------------------------------------------------------


def test_parse_fecha_8_digitos():
    from arca_fe.wsfe import _parse_fecha

    assert _parse_fecha("20241201") == date(2024, 12, 1)


def test_parse_fecha_iso():
    from arca_fe.wsfe import _parse_fecha

    assert _parse_fecha("2024-12-01") == date(2024, 12, 1)


def test_parse_fecha_none():
    from arca_fe.wsfe import _parse_fecha

    assert _parse_fecha(None) is None


def test_parse_fecha_vacio():
    from arca_fe.wsfe import _parse_fecha

    assert _parse_fecha("") is None


# ---------------------------------------------------------------------------
# Tests de parseo de respuesta FECAESolicitar
# ---------------------------------------------------------------------------


def _make_det(
    resultado: str,
    cae: Optional[str] = None,
    cae_vto: Optional[str] = None,
    cbte_desde: int = 1,
    obs: Optional[list] = None,
    errs: Optional[list] = None,
):
    """Construye un mock del FECAEDetResponse de zeep."""
    det = MagicMock()
    det.Resultado = resultado
    det.CAE = cae
    det.CAEFchVto = cae_vto
    det.CbteDesde = cbte_desde

    if obs:
        obs_container = MagicMock()
        obs_items = []
        for code, msg in obs:
            o = MagicMock()
            o.Code = code
            o.Msg = msg
            obs_items.append(o)
        obs_container.Obs = obs_items
        det.Observaciones = obs_container
    else:
        det.Observaciones = None

    if errs:
        err_container = MagicMock()
        err_items = []
        for code, msg in errs:
            e = MagicMock()
            e.Code = code
            e.Msg = msg
            err_items.append(e)
        err_container.Err = err_items
        det.Errors = err_container
    else:
        det.Errors = None

    return det


def _make_fecae_response(det, cab_errs: Optional[list] = None):
    resp = MagicMock()
    resp.FeDetResp.FECAEDetResponse = [det]
    if cab_errs:
        err_container = MagicMock()
        err_items = []
        for code, msg in cab_errs:
            e = MagicMock()
            e.Code = code
            e.Msg = msg
            err_items.append(e)
        err_container.Err = err_items
        resp.Errors = err_container
    else:
        resp.Errors = None
    return resp


def test_solicitar_cae_aprobado():
    """Resultado 'A' devuelve CAE + fecha de vencimiento."""
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    det = _make_det("A", cae="12345678901234", cae_vto="20241215", cbte_desde=5)
    mock_resp = _make_fecae_response(det)

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECAESolicitar.return_value = mock_resp
        mock_client_fn.return_value.service = mock_service

        result = client.solicitar_cae({})

    assert result.resultado == "A"
    assert result.cae == "12345678901234"
    assert result.cae_vto == date(2024, 12, 15)
    assert result.numero == 5
    assert result.errores == ()


def test_solicitar_cae_rechazado():
    """Resultado 'R' devuelve errores, sin CAE."""
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    det = _make_det("R", errs=[(10060, "CUIT del receptor no encontrado")])
    mock_resp = _make_fecae_response(det)

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECAESolicitar.return_value = mock_resp
        mock_client_fn.return_value.service = mock_service

        result = client.solicitar_cae({})

    assert result.resultado == "R"
    assert result.cae is None
    assert "10060" in result.errores[0]


def test_solicitar_cae_con_observaciones():
    """Resultado 'A' puede traer Observaciones no fatales."""
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    det = _make_det(
        "A",
        cae="99887766554433",
        cae_vto="20241231",
        cbte_desde=10,
        obs=[(502, "El campo FchServDesde no es obligatorio para este tipo")],
    )
    mock_resp = _make_fecae_response(det)

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECAESolicitar.return_value = mock_resp
        mock_client_fn.return_value.service = mock_service

        result = client.solicitar_cae({})

    assert result.resultado == "A"
    assert result.cae == "99887766554433"
    assert len(result.observaciones) == 1
    assert "502" in result.observaciones[0]


def test_ultimo_autorizado_mock():
    """FECompUltimoAutorizado devuelve int."""
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    mock_resp = MagicMock()
    mock_resp.CbteNro = 42
    mock_resp.Errors = None

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECompUltimoAutorizado.return_value = mock_resp
        mock_client_fn.return_value.service = mock_service

        nro = client.ultimo_autorizado(1, 1)

    assert nro == 42


def test_consultar_no_existe_devuelve_none():
    """FECompConsultar lanza Fault con código 10016 → devuelve None."""
    import zeep.exceptions
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECompConsultar.side_effect = zeep.exceptions.Fault(
            "El comprobante consultado no existe o no pertenece al contribuyente."
        )
        mock_client_fn.return_value.service = mock_service

        result = client.consultar(1, 1, 9999)

    assert result is None


def test_consultar_no_existe_por_error_602_combinacion_virgen():
    """602 = "no existen datos" para (pto_vta, cbte_tipo) SIN historial (ej. la
    primera Nota de Crédito de un punto de venta) — debe tratarse igual que
    10016, no como error real. Bug de prod: bloqueaba con un 503 espurio."""
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    err = MagicMock()
    err.Code = 602
    err.Msg = "No existen datos en nuestros registros para los parámetros ingresados."
    err_container = MagicMock()
    err_container.Err = [err]
    mock_resp = MagicMock()
    mock_resp.Errors = err_container

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECompConsultar.return_value = mock_resp
        mock_client_fn.return_value.service = mock_service

        result = client.consultar(2, 13, 1)

    assert result is None


def test_consultar_error_real_no_se_confunde_con_no_existe():
    """Un error de AFIP que NO es 10016/602 tiene que seguir levantando."""
    from arca_fe.wsfe import WsfeClient

    client = WsfeClient("wswhomo.afip.gov.ar", 20123456789, "tok", "sig")

    err = MagicMock()
    err.Code = 500
    err.Msg = "Error interno de AFIP"
    err_container = MagicMock()
    err_container.Err = [err]
    mock_resp = MagicMock()
    mock_resp.Errors = err_container

    with patch.object(client, "_client") as mock_client_fn:
        mock_service = MagicMock()
        mock_service.FECompConsultar.return_value = mock_resp
        mock_client_fn.return_value.service = mock_service

        with pytest.raises(RuntimeError, match="500"):
            client.consultar(2, 13, 1)
